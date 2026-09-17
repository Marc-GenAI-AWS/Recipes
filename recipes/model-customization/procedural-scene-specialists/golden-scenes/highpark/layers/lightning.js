import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G } from '../prelude.glsl.js';
import { SADDLE } from '../field.js';

const smoothstep2 = (x, a, b) => { const t = THREE.MathUtils.clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

/* ═══ COMPONENT: Lightning (effects) ═══
   A jagged additive bolt in the saddle gap + synthesized thunder, gated to the
   storm state. Writes the shared uFlash channel (sky/grass/prairie/matter read
   it; PostFX boosts bloom/exposure from it). Note: this.ctx is the AudioContext,
   so scene refs are held separately. */
export class Lightning {
  constructor(sctx) {
    const { scene, U, rr } = sctx;
    this.U = U; this.camera = sctx.camera; this.rnd = sctx.rnd; this.rr = rr; this.cur = sctx.cur;
    this.env = 0; this.next = rr(2.5, 6); this.t0 = -100; this.boltSeed = 0; this.ctx = null;
    /* a jagged bolt drawn on an additive plane standing in the saddle gap */
    const g = new THREE.PlaneGeometry(34, 120, 1, 1);
    this.bolt = new THREE.Mesh(g, new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      uniforms: uniformsFor(U, { uEnv: F(0), uSeed: F(0) }),
      vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`uniform float uEnv, uSeed; varying vec2 vUv;
      void main(){ if (uEnv < 0.02) discard;
        float y = 1.0 - vUv.y;                                                        /* strike from the top down */
        /* jagged centreline: low-freq wander + a couple of sharp kinks */
        float cx = 0.5 + 0.20 * (fbm2(vec2(y * 9.0 + uSeed * 40.0, uSeed)) - 0.47)
                       + 0.10 * (fract(y * 3.0 + uSeed) - 0.5)
                       + 0.03 * sin(y * 80.0 + uSeed * 12.0);
        float d = abs(vUv.x - cx);
        float core = smoothstep(0.022, 0.0, d);                                       /* crisp white filament */
        float glow = smoothstep(0.13, 0.0, d) * 0.35;                                 /* tight halo */
        /* two forked branches peeling off partway down */
        float bx = cx + 0.22 * sign(fract(uSeed * 9.0) - 0.5);
        float branch = smoothstep(0.016, 0.0, abs(vUv.x - bx * 0.5 - cx * 0.5)) * smoothstep(0.35, 0.05, abs(y - 0.6)) * step(0.5, fract(y * 5.0 + uSeed));
        float a = (core + glow + branch * 0.7) * uEnv * smoothstep(0.0, 0.05, vUv.y) * smoothstep(1.0, 0.92, vUv.y);
        gl_FragColor = vec4(FLASH_C * (3.0 + core * 6.0), a); }` }));
    this.bolt.position.set(SADDLE.x - 60, SADDLE.y + 55, SADDLE.z + 70); this.bolt.renderOrder = 8; scene.add(this.bolt);
    /* thunder is synthesized (no audio assets); only after a user gesture unlocks audio */
    const unlock = () => { try { if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)(); if (this.ctx.state === 'suspended') this.ctx.resume(); } catch (e) {} };
    window.addEventListener('pointerdown', unlock, { once: false });
  }
  strike() { this.t0 = this.U.uTime.value; this.boltSeed = this.rnd(); this.bolt.material.uniforms.uSeed.value = this.boltSeed;
    this.bolt.position.x = SADDLE.x + (this.rnd() < 0.5 ? this.rr(-78, -34) : this.rr(34, 78)); this.thunder(); }   /* off to one side, over the peaks */
  thunder() {
    try {
      const ctx = this.ctx; if (!ctx || ctx.state !== 'running') return;
      const now = ctx.currentTime, delay = 0.5 + this.rnd() * 1.6, dur = 1.6 + this.rnd() * 1.4;   /* delay ≈ distance to the strike */
      const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * dur), ctx.sampleRate), ch = buf.getChannelData(0);
      let last = 0; for (let i = 0; i < ch.length; i++) { const w = Math.random() * 2 - 1; last = (last + 0.02 * w) / 1.02; ch[i] = last * 3.2; }   /* brown noise */
      const src = ctx.createBufferSource(); src.buffer = buf;
      const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 240; lp.Q.value = 0.7;
      const gn = ctx.createGain(); gn.gain.setValueAtTime(0, now + delay);
      gn.gain.linearRampToValueAtTime(0.45, now + delay + 0.08);
      gn.gain.exponentialRampToValueAtTime(0.0008, now + delay + dur);
      src.connect(lp); lp.connect(gn); gn.connect(ctx.destination); src.start(now + delay); src.stop(now + delay + dur);
    } catch (e) {}
  }
  update(dt, t) {
    const cur = this.cur;
    if (cur.rain > 0.5) { this.next -= dt; if (this.next <= 0) { this.strike(); this.next = this.rr(3.5, 9); } }
    const e = t - this.t0;
    /* double-flicker envelope with a fast decay */
    this.env = e < 0.45 ? Math.max(0, Math.exp(-e * 7.0) * (0.55 + 0.45 * Math.sin(e * 85.0)) * Math.min(1, e / 0.02)) * cur.rain : 0;
    this.U.uFlash.value = this.env;
    const be = smoothstep2(e, 0.0, 0.015) * (1.0 - smoothstep2(e, 0.10, 0.34));   /* a crisp stroke, held ~0.3s */
    this.bolt.material.uniforms.uEnv.value = (e >= 0.0 && e < 0.45 ? be : 0.0) * cur.rain;
    this.bolt.lookAt(this.camera.position.x, this.bolt.position.y, this.camera.position.z);
  }
}
