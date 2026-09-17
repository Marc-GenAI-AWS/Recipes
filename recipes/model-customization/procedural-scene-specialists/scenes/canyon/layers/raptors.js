import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { RIM, meander } from '../field.js';

/* ═══ COMPONENT: Raptors (the fauna) ═══
   Birds of prey riding the updraft in the slot: they circle on held wings, bank
   into the turn, and cross the bright ribbon of sky where they read as silhouettes.

   Scale is the thing to get right — a raptor is ~2 units across at a wingspan the
   camera sees from 20-60 units away. Too small and they read as grit on the lens;
   too large and the canyon stops looking deep. */
export class Raptors {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr } = ctx;
    const N = 7;

    this.birds = [];
    for (let i = 0; i < N; i++) {
      this.birds.push({
        cx: rr(-6, 6), cz: rr(-70, 70),          // the thermal it circles
        r: rr(9, 22), y: rr(6, RIM - 6),
        w: rr(0.10, 0.22) * (rr(0, 1) < 0.5 ? -1 : 1),   // angular speed + direction
        ph: rr(0, Math.PI * 2), flap: rr(0.7, 1.5), span: rr(1.6, 2.6),
      });
    }

    const geo = birdGeometry();
    this.mesh = new THREE.InstancedMesh(geo, raptorMat(ctx), N);
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);

    this.m = new THREE.Matrix4(); this.q = new THREE.Quaternion();
    this.p = new THREE.Vector3(); this.s = new THREE.Vector3();
    this.e = new THREE.Euler();
  }

  update(dt, t) {
    const { m, q, p, s, e } = this;
    for (let i = 0; i < this.birds.length; i++) {
      const b = this.birds[i];
      const a = b.ph + t * b.w;
      const x = b.cx + Math.cos(a) * b.r + meander(b.cz) * 0.35;
      const z = b.cz + Math.sin(a) * b.r;
      const y = b.y + 1.6 * Math.sin(t * 0.21 + b.ph);
      p.set(x, y, z);
      // face along the tangent of the circle, and bank into it
      const heading = a + (b.w > 0 ? Math.PI / 2 : -Math.PI / 2);
      e.set(0.12 * Math.sin(t * b.flap + b.ph), heading, b.w > 0 ? -0.42 : 0.42, 'YXZ');
      q.setFromEuler(e);
      s.setScalar(b.span);
      this.mesh.setMatrixAt(i, m.compose(p, q, s));
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}

/* a flat delta: body spine plus two swept wings, enough to read as a raptor
   in silhouette against the sky, which is how it is nearly always seen. */
function birdGeometry() {
  const g = new THREE.BufferGeometry();
  const pos = [
    0, 0, -0.55, 0, 0, 0.45,             // spine
    -0.5, 0.05, 0.12, -0.16, 0, -0.1,    // left wing
    0.5, 0.05, 0.12, 0.16, 0, -0.1,      // right wing
  ];
  const idx = [0, 3, 2, 0, 2, 1, 0, 1, 4, 0, 4, 5];
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

const raptorMat = (ctx) => new THREE.ShaderMaterial({
  side: THREE.DoubleSide,
  uniforms: uniformsFor(ctx.U, { uBirdC: F(new THREE.Color(0.10, 0.08, 0.07)) }),
  vertexShader: /* glsl */`
    varying vec3 vP, vN;
    void main(){
      #ifdef USE_INSTANCING
      mat4 m = modelMatrix * instanceMatrix;
      #else
      mat4 m = modelMatrix;
      #endif
      vec4 wp = m * vec4(position, 1.0);
      vP = wp.xyz; vN = normalize(mat3(m) * normal);
      gl_Position = projectionMatrix * viewMatrix * wp; }`,
  fragmentShader: G + /* glsl */`
    varying vec3 vP, vN; uniform vec3 uBirdC;
    void main(){
      vec3 n = normalize(vN);
      float lam = max(dot(n, -uSunDir), 0.0);
      /* mostly silhouette: a little sun on the upper surface, sky fill from above */
      vec3 col = uBirdC * (0.30 + 0.9 * lam) + uSkyC * uSkyI * 0.18 * (0.4 + 0.6 * max(n.y, 0.0));
      gl_FragColor = vec4(haze(col, vP), 1.0);
    ` + TAIL,
});
