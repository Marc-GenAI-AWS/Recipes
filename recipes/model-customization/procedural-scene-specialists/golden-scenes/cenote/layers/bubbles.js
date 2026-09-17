import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { floorH } from '../field.js';

/* ═══ COMPONENT: Bubbles ═══
   Rising from vents on the mound, fresnel shells lit inside the beam / by the
   torch. Density gated by cur.bubbles. */
export class Bubbles {
  constructor(ctx) {
    const { scene, U, rnd, rr } = ctx;
    this.ctx = ctx;
    this.N = 110; this.b = []; const vents = [[1.5, 1.0], [-2.2, -1.6], [4.0, -3.2]];
    for (let i = 0; i < this.N; i++) { const v = vents[i % 3]; this.b.push({ x: v[0] + rr(-0.4, 0.4), z: v[1] + rr(-0.4, 0.4), y: rr(-15, -0.5), v: rr(0.8, 1.5), s: rr(0.05, 0.16), ph: rnd() * 6.283 }); }
    this.mesh = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 10, 8), new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, {}), transparent: true, depthWrite: false,
      vertexShader: `varying vec3 vP, vN; void main(){ mat4 m = modelMatrix * instanceMatrix; vec4 wp = m * vec4(position, 1.0); vP = wp.xyz; vN = normalize(mat3(m) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP, vN;
      void main(){ vec3 n = normalize(vN), V = normalize(cameraPosition - vP); float f = pow(1.0 - max(dot(n, V), 0.0), 2.5), bm = beamMask(vP);
        vec3 col = mix(uFogTop * 1.5, vec3(0.9, 0.97, 1.0), f) * (0.45 + 0.9 * bm + uSunI * 0.25) + torch(vP, n) * 0.9;
        gl_FragColor = vec4(fog(col, vP), 0.16 + 0.7 * f);` + TAIL }), this.N);
    this.mesh.renderOrder = 4; scene.add(this.mesh); this.d = new THREE.Object3D();
  }
  update(dt, t) {
    const cur = this.ctx.cur, d = this.d, N = this.N;
    for (let i = 0; i < N; i++) {
      const b = this.b[i]; b.y += b.v * dt * (0.6 + 0.6 * cur.bubbles);
      if (b.y > -0.15) { b.y = floorH(b.x, b.z) + 0.3; }
      const vis = THREE.MathUtils.clamp((cur.bubbles * N - i) * 0.4, 0, 1), grow = 1 + 0.35 * THREE.MathUtils.smoothstep(b.y, -15, 0);
      d.position.set(b.x + 0.25 * Math.sin(t * 2.1 + b.ph), b.y, b.z + 0.25 * Math.cos(t * 1.7 + b.ph)); d.scale.setScalar(b.s * grow * vis); d.updateMatrix(); this.mesh.setMatrixAt(i, d.matrix);
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}
