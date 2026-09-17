import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { HALO_Y } from '../field.js';

/* ═══ COMPONENT: Halocline ═══
   Hazy fresh/salt interface layer at y ≈ -11: two translucent discs, brightest
   at grazing angles and where the beam crosses them. */
export class Halocline {
  constructor(ctx) {
    const { scene, U } = ctx;
    const mat = new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, { uHalo: U.uHalo }), transparent: true, depthWrite: false, side: THREE.DoubleSide,
      vertexShader: `varying vec3 vP; void main(){ vP = (modelMatrix * vec4(position, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP; uniform float uHalo;
      void main(){ float n1 = fbm2(vP.xz * 0.11 + uTime * vec2(0.03, 0.02)), n2 = fbm2(vP.xz * 0.45 - uTime * vec2(0.05, 0.03) + 5.0);
        vec3 V = normalize(vP - cameraPosition); float graze = 1.0 - abs(V.y);
        float a = uHalo * (0.22 + 0.55 * n1) * (0.7 + 0.3 * n2) * (0.35 + 0.9 * graze) * smoothstep(27.0, 18.0, length(vP.xz));
        vec3 col = mix(uFogDeep, vec3(0.7, 0.82, 0.86), 0.3) * (0.5 + 1.1 * beamMask(vP)) + torchAt(vP) * 0.3;
        gl_FragColor = vec4(fog(col, vP), a * 0.45);` + TAIL });
    for (const dy of [0, -0.9]) { const m = new THREE.Mesh(new THREE.CircleGeometry(28, 48), mat); m.rotation.x = -Math.PI / 2; m.position.y = HALO_Y + dy; m.renderOrder = 2; scene.add(m); }
  }
}
