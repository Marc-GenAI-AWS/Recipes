import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { groundH } from '../field.js';

/* ═══ COMPONENT: Mist ═══
   Dawn mist ribbons lying in the creek hollows; brighten where the shaft
   crosses them, gated by uMist. */
export class Mist {
  constructor(ctx) {
    const { scene, U, rr } = ctx;
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, uniforms: uniformsFor(U, {}),
      vertexShader: `varying vec2 vUv; varying vec3 vP; void main(){ vUv = uv; vP = (modelMatrix * vec4(position, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      uniform float uMist; varying vec2 vUv; varying vec3 vP;
      void main(){ float n = fbm2(vUv * vec2(5.0, 1.6) + vec2(uTime * 0.018, 0.0)) * 0.5 + 0.5;
        float a = smoothstep(0.0, 0.25, vUv.y) * smoothstep(1.0, 0.55, vUv.y)
                * smoothstep(0.0, 0.12, vUv.x) * smoothstep(1.0, 0.88, vUv.x) * n * 0.5 * uMist;
        vec3 col = uFogC * (0.85 + 0.3 * uSunI) + uSunC * shaftMask(vP) * 0.5;
        gl_FragColor = vec4(fog(col, vP), a);` + TAIL });
    for (let i = 0; i < 5; i++) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(220, 8), mat);
      const z = -30 - i * 32; m.position.set(rr(-25, 40), groundH(20, z) + 2.2, z); m.renderOrder = 2; scene.add(m);
    }
  }
}
