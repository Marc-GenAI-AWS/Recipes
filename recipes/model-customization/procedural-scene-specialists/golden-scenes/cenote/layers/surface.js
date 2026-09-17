import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Surface ═══
   Underside of the water: Snell's window, total internal reflection at grazing
   angles, sun glints, rain rings in the storm state. */
export class Surface {
  constructor(ctx) {
    const { scene, U } = ctx;
    const m = new THREE.Mesh(new THREE.CircleGeometry(27.5, 64), new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, {}), transparent: true, depthWrite: false, side: THREE.DoubleSide,
      vertexShader: `varying vec3 vP; void main(){ vP = (modelMatrix * vec4(position, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP; uniform float uRipple, uRain;
      float h(vec2 q){ float t = uTime; float w = uRipple * (0.14 * sin(q.x * 0.8 + t * 1.2) + 0.09 * sin(q.x * 0.5 + q.y * 0.9 - t * 0.8) + 0.06 * sin(q.y * 1.7 + t * 1.6) + 0.05 * sin((q.x - q.y) * 2.3 + t * 2.1));
        return w + uRain * 0.09 * (fbm2(q * 2.2 + t * vec2(1.9, 1.4)) - 0.5); }
      void main(){ vec2 q = vP.xz; float e = 0.06, h0 = h(q);
        vec3 n = normalize(vec3(-(h(q + vec2(e, 0.0)) - h0) / e, 1.0, -(h(q + vec2(0.0, e)) - h0) / e));
        vec3 V = normalize(vP - cameraPosition); float cosI = dot(V, n);
        float win = smoothstep(0.56, 0.74, cosI);                                  /* Snell's window */
        vec3 refl = mix(uFogDeep * 0.55, uFogTop * 0.9, smoothstep(0.05, 0.5, cosI)) * (0.75 + 0.9 * (n.x + n.z));
        vec3 T = refract(V, -n, 1.33); float sunDot = max(dot(T, -uSunDir), 0.0) * step(0.001, length(T));   /* sun seen through the ripples */
        float glint = pow(sunDot, 180.0) * uSunI * 2.0 + pow(sunDot, 5.0) * uSunI * 0.35;
        float entry = beamMask(vP - vec3(0.0, 0.6, 0.0)) * uSunI * 0.16;                                 /* the bright patch where the beam enters */
        vec3 col = mix(refl, uFogTop * 0.5, win) + uSunC * (glint + entry) + torch(vP, -n) * 0.5;
        float a = mix(0.72, 0.3, win) + glint * 0.3;
        gl_FragColor = vec4(fog(col, vP), a);` + TAIL }));
    m.rotation.x = Math.PI / 2; m.renderOrder = 3; scene.add(m);
  }
}
