import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Fluff ═══
   Wind-borne seed motes that catch the shafts; blow east and recycle, gated
   by cur.fluff. */
export class Fluff {
  constructor(ctx) {
    const { scene, U, rnd, rr, renderer } = ctx;
    this.ctx = ctx;
    const N = 1600, p = new Float32Array(N * 3), s = new Float32Array(N);
    for (let i = 0; i < N; i++) { p.set([rr(-110, 110), rr(0.5, 22), rr(-150, 25)], i * 3); s[i] = rnd(); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('aSeed', new THREE.BufferAttribute(s, 1));
    const pts = new THREE.Points(g, new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: uniformsFor(U, { uFluff: F(0.5), uPx: F(renderer.getPixelRatio()) }),
      vertexShader: G + /* glsl */`
      attribute float aSeed; uniform float uFluff, uPx; varying float vB, vA;
      void main(){ vec3 p = position;
        p.x = mod(p.x + uTime * (1.5 + 2.5 * aSeed) * (0.4 + uWind) + 110.0, 220.0) - 110.0;
        p.y += sin(uTime * 0.7 + aSeed * 20.0) * 1.6; p.z += sin(uTime * 0.23 + aSeed * 9.0) * 4.0;
        float sm = shaftMask(p);
        vB = (0.10 + 0.25 * uSunI * cloudShad(p) + 2.2 * sm) * fogAtt(p);
        vA = uFluff * step(aSeed, uFluff) * (0.5 + 1.5 * sm);
        vec4 mv = viewMatrix * vec4(p, 1.0);
        gl_PointSize = min((0.9 + 1.4 * aSeed) * uPx * 32.0 / max(-mv.z, 1.0), 5.0);
        gl_Position = projectionMatrix * mv; }`,
      fragmentShader: /* glsl */`
      varying float vB, vA;
      void main(){ float r = length(gl_PointCoord - 0.5) * 2.0; float m = smoothstep(1.0, 0.3, r);
        gl_FragColor = vec4(vec3(1.0, 0.96, 0.86) * vB, m * vA * 0.55);` + TAIL }));
    pts.renderOrder = 6; scene.add(pts);
    this.mat = pts.material;
  }
  update() { this.mat.uniforms.uFluff.value = this.ctx.cur.fluff; }
}
