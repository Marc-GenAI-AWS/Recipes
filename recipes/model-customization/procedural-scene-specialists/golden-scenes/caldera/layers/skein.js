import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { BOWL } from '../field.js';

/* ═══ COMPONENT: Skein (the fauna) ═══
   Almost nothing crosses a live caldera, and this layer does not pretend otherwise:
   nine big soarers, high up, riding the thermal that stands over the hot pan — and
   circling wide of the vents, because the column over a vent is ash, not lift.

   The reason they are worth drawing at all is that they are the one thing in frame
   that shows what the light is doing. A bird over a lit floor is not a silhouette:
   its UNDERSIDE is the lit face and its back is the dark one, so each one reads as
   a small orange chevron with a black spine. Get that backwards and the whole
   lighting claim of the world collapses in the only place the eye can check it.

   Scale: ~4 units of wingspan seen from 40-90 units away. Smaller and they are
   sensor noise; larger and the caldera stops being 240 units across. */
export class Skein {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr } = ctx;
    const N = 12;
    this.birds = [];
    for (let i = 0; i < N; i++) {
      const ca = rr(0, Math.PI * 2), cr = rr(56, BOWL - 14);
      this.birds.push({
        cx: Math.cos(ca) * cr, cz: Math.sin(ca) * cr,
        r: rr(14, 30), y: rr(22, 48),
        w: rr(0.09, 0.19) * (rr(0, 1) < 0.5 ? -1 : 1),
        ph: rr(0, Math.PI * 2), flap: rr(0.5, 1.1), span: rr(1.1, 1.8),
      });
    }
    this.mesh = new THREE.InstancedMesh(soarerGeometry(), skeinMat(ctx), N);
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);

    this.m = new THREE.Matrix4(); this.q = new THREE.Quaternion();
    this.p = new THREE.Vector3(); this.s = new THREE.Vector3(); this.e = new THREE.Euler();
  }

  update(dt, t) {
    const { m, q, p, s, e } = this;
    const rate = this.ctx.cur ? (this.ctx.cur.birdRate ?? 1) : 1;
    for (let i = 0; i < this.birds.length; i++) {
      const b = this.birds[i];
      const a = b.ph + t * b.w * rate;
      p.set(b.cx + Math.cos(a) * b.r, b.y + 2.6 * Math.sin(t * 0.17 * rate + b.ph), b.cz + Math.sin(a) * b.r);
      const heading = a + (b.w > 0 ? Math.PI / 2 : -Math.PI / 2);
      e.set(0.10 * Math.sin(t * b.flap * rate + b.ph), heading, b.w > 0 ? -0.36 : 0.36, 'YXZ');
      q.setFromEuler(e);
      s.setScalar(b.span);
      this.mesh.setMatrixAt(i, m.compose(p, q, s));
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}

/* a flat delta with a dihedral kink, so the two wing halves take the seam light at
   slightly different angles and the bird does not flatten into one orange dash. */
function soarerGeometry() {
  const g = new THREE.BufferGeometry();
  const pos = [
    0, 0, -0.62, 0, 0, 0.52,               // 0,1 head / tail
    -0.34, 0.05, -0.05, -0.95, 0.13, 0.30, // 2,3 left inner / swept tip
    0.34, 0.05, -0.05, 0.95, 0.13, 0.30,   // 4,5 right inner / swept tip
  ];
  const idx = [0, 2, 1, 2, 3, 1, 0, 1, 4, 1, 5, 4];
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

const skeinMat = (ctx) => new THREE.ShaderMaterial({
  side: THREE.DoubleSide,
  uniforms: uniformsFor(ctx.U, { uSoarC: F(new THREE.Color(0.105, 0.090, 0.085)) }),
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
    varying vec3 vP, vN; uniform vec3 uSoarC;
    void main(){
      /* a soarer is a thin plate: orient the normal toward the eye so the face we
         can actually see is the one that gets shaded, then let fireLight() decide.
         Seen from the pan that is the UNDERSIDE, and it comes up orange. */
      vec3 n = normalize(vN);
      if (dot(n, normalize(cameraPosition - vP)) < 0.0) n = -n;
      vec3 col = uSoarC * (0.10 + 3.6 * fireLight(vP, n)) + uSoarC * vaultLight(n) * 0.9;
      col += uLavaC * uCrackI * 0.16 * max(-n.y, 0.0);      /* seam rim on the leading edge */
      gl_FragColor = vec4(ashVeil(col, vP), 1.0);
    ` + TAIL,
});
