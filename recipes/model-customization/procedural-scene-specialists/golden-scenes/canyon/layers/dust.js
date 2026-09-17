import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { LEN, HALF } from '../field.js';

/* ═══ COMPONENT: Dust (the effects layer) ═══
   Airborne grit in the canyon air: fine motes that drift on uWind, catch the light
   where the sun reaches down the slot, and thicken hugely in the dust-storm state.
   Additive points, so they brighten the air without occluding the rock behind. */
export class Dust {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr } = ctx;
    const N = 4200;
    const p = new Float32Array(N * 3), seed = new Float32Array(N), size = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      p[i * 3] = rr(-HALF, HALF);
      p[i * 3 + 1] = rr(-1, 40);
      p[i * 3 + 2] = rr(-LEN / 2, LEN / 2);
      seed[i] = rr(0, 100);
      size[i] = rr(0.6, 2.6);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(p, 3));
    g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
    g.setAttribute('aSize', new THREE.BufferAttribute(size, 1));

    this.mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: uniformsFor(ctx.U, { uSpan: F(LEN), uHalf: F(HALF) }),
      vertexShader: G + /* glsl */`
        attribute float aSeed; attribute float aSize;
        varying float vFade; varying vec3 vP;
        uniform float uSpan, uHalf;
        void main(){
          vec3 q = position;
          /* drift downwind and settle slowly, wrapping inside the corridor */
          vec2 w = windAt(q);
          q.x += w.x * uTime * 1.6 + 1.2 * sin(uTime * 0.5 + aSeed);
          q.z += w.y * uTime * 1.6 + 1.2 * cos(uTime * 0.4 + aSeed * 1.7);
          q.y -= mod(uTime * (0.15 + 0.25 * aSize) + aSeed, 44.0) - 2.0;
          q.x = mod(q.x + uHalf, uHalf * 2.0) - uHalf;
          q.z = mod(q.z + uSpan * 0.5, uSpan) - uSpan * 0.5;
          q.y = mod(q.y + 4.0, 44.0) - 4.0;
          vP = q;
          /* brightest where the sun reaches down the slot */
          vFade = (0.25 + 0.75 * slotLight(q)) * (0.35 + 1.3 * uDust);
          vec4 mv = viewMatrix * vec4(q, 1.0);
          gl_PointSize = aSize * (170.0 / max(-mv.z, 1.0));
          gl_Position = projectionMatrix * mv; }`,
      fragmentShader: G + /* glsl */`
        varying float vFade; varying vec3 vP;
        void main(){
          vec2 d = gl_PointCoord - 0.5;
          float a = smoothstep(0.5, 0.0, length(d));
          vec3 col = mix(uHazeC, uSunC, 0.55) * uSunI * vFade;
          gl_FragColor = vec4(col * a, a * vFade * 0.5 * hazeAtt(vP));
        ` + TAIL,
    });

    this.points = new THREE.Points(g, this.mat);
    this.points.frustumCulled = false;
    ctx.scene.add(this.points);
  }
  update() { /* motion is uTime/uWind driven in the vertex shader */ }
}
