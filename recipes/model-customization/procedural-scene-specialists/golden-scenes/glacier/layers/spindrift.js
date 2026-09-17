import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Spindrift (the effects layer) ═══
   Two things are always in the air here. Low down, spindrift: dry snow the katabatic
   wind peels off the surface and runs downhill in sheets, so the ice appears to be
   smoking. Higher up, diamond dust: ice crystals suspended in air too cold to hold
   vapour, which do nothing at all until they turn edge-on to the sun and flare.

   Additive points, so they brighten the air rather than occluding the ice — a
   snowfield does not get darker when it is blowing, it gets more featureless. The
   wrap box follows the camera, so density stays where it can be seen instead of
   being spread thin over three hundred metres of basin. */
const SPAN = 120;

export class Spindrift {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr, rnd } = ctx;
    const N = 5200;
    const pos = new Float32Array(N * 3), seed = new Float32Array(N);
    const size = new Float32Array(N), kind = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      pos[i * 3] = rr(-SPAN / 2, SPAN / 2);
      pos[i * 3 + 1] = 0;
      pos[i * 3 + 2] = rr(-SPAN / 2, SPAN / 2);
      seed[i] = rr(0, 100);
      const dust = rnd() < 0.34;
      kind[i] = dust ? 1 : 0;
      size[i] = dust ? rr(0.5, 1.4) : rr(0.8, 3.0);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
    g.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
    g.setAttribute('aKind', new THREE.BufferAttribute(kind, 1));

    this.mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: uniformsFor(ctx.U, { uSpan: F(SPAN) }),
      vertexShader: G + /* glsl */`
        attribute float aSeed; attribute float aSize; attribute float aKind;
        varying float vGlow; varying float vKind; varying vec3 vQ;
        uniform float uSpan;
        /* the dominant analytic terms of iceH(): enough for a sheet of snow that is
           itself metres thick to hug the surface without a height texture */
        float iceY(vec2 w){ float xc = w.x - (6.0 * sin(w.y * 0.012) + 2.5 * sin(w.y * 0.031 + 1.1));
          return -w.y * 0.095 + 3.4 * exp(-xc * xc / 1800.0); }
        void main(){
          vec3 q = position;
          vec2 w = gustAt(q) * (2.0 + 9.0 * uDrift);
          q.xz += w * uTime * 3.0 + vec2(sin(uTime * 1.1 + aSeed), cos(uTime * 0.9 + aSeed * 1.7)) * 1.4;
          vec2 c = cameraPosition.xz;
          q.x = mod(q.x - c.x + uSpan * 0.5, uSpan) - uSpan * 0.5 + c.x;
          q.z = mod(q.z - c.y + uSpan * 0.5, uSpan) - uSpan * 0.5 + c.y;
          float f = fract(aSeed * 13.13);
          float h = (aKind > 0.5)
            ? 3.0 + 34.0 * f + 1.2 * sin(uTime * 0.4 + aSeed)                    /* diamond dust */
            : 0.10 + 3.4 * f * f + 0.55 * sin(uTime * 1.9 + aSeed * 7.0);        /* spindrift sheet */
          q.y = iceY(q.xz) + h;
          vQ = q; vKind = aKind;
          /* crystals flare only when they turn to the sun; blown snow is simply lit */
          float flare = 0.5 + 0.5 * sin(uTime * 5.5 + aSeed * 31.0);
          vGlow = (aKind > 0.5)
            ? smoothstep(0.55, 1.0, flare) * (0.35 + 1.5 * uGlintI)
            : (0.30 + 1.8 * uDrift) * (1.0 - 0.55 * smoothstep(0.0, 3.4, h));
          vec4 mv = viewMatrix * vec4(q, 1.0);
          /* grains, not lens smudges: clamp hard so a particle that drifts past the
             near plane does not become a soft white disc across half the frame */
          gl_PointSize = clamp(aSize * (26.0 / max(-mv.z, 1.0)) * (aKind > 0.5 ? 0.8 : 1.0), 1.0, 7.0);
          gl_Position = projectionMatrix * mv; }`,
      fragmentShader: G + /* glsl */`
        varying float vGlow; varying float vKind; varying vec3 vQ;
        void main(){
          vec2 d = gl_PointCoord - 0.5;
          float r = length(d);
          /* dust is a hard spark with a cross flare; spindrift is a soft smear */
          float a = (vKind > 0.5)
            ? smoothstep(0.42, 0.0, r) + 0.35 * smoothstep(0.5, 0.0, min(abs(d.x), abs(d.y)) * 6.0)
            : smoothstep(0.5, 0.0, r) * 0.85;
          vec3 col = mix(mix(uSnowC, uSolarC, 0.45), vec3(0.78, 0.90, 1.0), 0.35 * vKind);
          col *= (0.45 + 0.9 * uSolarI) * vGlow;
          gl_FragColor = vec4(col * a, clamp(a * vGlow * 0.55, 0.0, 1.0) * aerialAtt(vQ));
        ` + TAIL,
    });

    this.points = new THREE.Points(g, this.mat);
    this.points.frustumCulled = false;
    ctx.scene.add(this.points);
  }
  update() { /* motion is uTime/uGustV driven in the vertex shader */ }
}
