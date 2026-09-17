import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { SADDLE } from '../field.js';

/* ═══ COMPONENT: Shafts (the hero) ═══
   Additive light blades hanging from the saddle along uShaftDir; brightness
   follows the shared shaftMask so the visible blades and the light on the
   ground always agree. */
export class Shafts {
  constructor(ctx) {
    const { scene, U, rr } = ctx;
    this.ctx = ctx;
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, uniforms: uniformsFor(U, {}),
      vertexShader: `varying vec3 vP; varying vec2 vUv; void main(){ vUv = uv; vP = (modelMatrix * vec4(position, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP; varying vec2 vUv;
      void main(){ float edge = smoothstep(0.0, 0.3, vUv.x) * smoothstep(1.0, 0.7, vUv.x);
        float blade = pow(edge, 1.4) * (0.45 + 0.55 * fbm2(vec2(vUv.x * 6.0, vUv.y * 2.0 - uTime * 0.10)));
        float a = shaftMask(vP) * blade * (1.0 - vUv.y * 0.5) * fogAtt(vP);
        gl_FragColor = vec4(uSunC * a * 1.8, 1.0);` + TAIL });
    this.group = new THREE.Group();
    for (let i = 0; i < 7; i++) {
      const w = rr(4, 9), m = new THREE.Mesh(new THREE.PlaneGeometry(w, 300, 1, 1), mat);
      m.userData.off = new THREE.Vector3(rr(-28, 28), 0, rr(-10, 10)); m.userData.rot = rr(-0.12, 0.12);
      this.group.add(m);
    }
    this.group.renderOrder = 5; scene.add(this.group);
  }
  update() {
    const dir = this.ctx.U.uShaftDir.value;
    for (const m of this.group.children) {
      /* each blade hangs from a point near the saddle and follows the shaft direction */
      m.position.copy(SADDLE).add(m.userData.off).addScaledVector(dir, 140);
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().negate());
      m.rotateY(m.userData.rot);
    }
  }
}
