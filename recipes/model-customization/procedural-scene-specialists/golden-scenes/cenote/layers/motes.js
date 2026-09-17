import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Motes ═══
   Silt in the water that lights up inside the beam / torch. Additive points
   that drift up and recycle. */
export class Motes {
  constructor(ctx) {
    const { scene, U, rnd, rr } = ctx;
    const N = 2600, p = new Float32Array(N * 3), s = new Float32Array(N);
    for (let i = 0; i < N; i++) { p[i * 3] = rr(-15, 15); p[i * 3 + 1] = rr(-15.8, -0.3); p[i * 3 + 2] = rr(-15, 15); s[i] = rnd(); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('aSeed', new THREE.BufferAttribute(s, 1));
    const pts = new THREE.Points(g, new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, { uPartA: U.uPartA, uPartC: U.uPartC }), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: G + /* glsl */`
      attribute float aSeed; varying float vB, vS;
      void main(){ vec3 p = position; float sp = 0.06 + 0.09 * aSeed;
        p.y = -0.3 - mod((-0.3 - p.y) + uTime * sp, 15.5); p.x += 0.5 * sin(uTime * 0.25 + aSeed * 6.283); p.z += 0.5 * cos(uTime * 0.2 + aSeed * 4.0);
        vec4 mv = viewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
        float bm = beamMask(p); vec3 tl = torchAt(p); vB = 0.05 + 1.5 * bm + 1.2 * (tl.r + tl.g); vS = aSeed;
        float d = distance(p, cameraPosition); float k = smoothstep(uHaloY - 1.5, uHaloY + 1.5, p.y); float fd = mix(uFogDD, uFogDT, k);
        vB *= exp(-d * d * fd * fd);
        gl_PointSize = min((0.8 + 1.5 * aSeed) * (0.7 + 0.8 * bm) * (28.0 / max(-mv.z, 1.0)), 6.0); }`,
      fragmentShader: /* glsl */`
      uniform vec3 uPartC; uniform float uPartA; varying float vB, vS;
      void main(){ float r = length(gl_PointCoord - 0.5) * 2.0; float m = smoothstep(1.0, 0.25, r);
        gl_FragColor = vec4(uPartC * vB, m * uPartA * (0.35 + 0.65 * vS) * min(vB, 1.0));` + TAIL }));
    pts.renderOrder = 6; scene.add(pts);
  }
}
