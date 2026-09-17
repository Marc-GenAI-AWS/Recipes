import * as THREE from 'three';
import { boot, F, C3 } from '../contract/runtime.js';
import { NLAMP, KERB_X, FACE_X } from './field.js';
import { Overcast } from './layers/overcast.js';
import { Blacktop } from './layers/blacktop.js';
import { Kerbside } from './layers/kerbside.js';
import { Passersby } from './layers/passersby.js';
import { Downpour } from './layers/downpour.js';
import { CameraRig } from './camera.js';
import { PostFX } from './postfx.js';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE: Citynight — a rain-wet street after dark.
   There is no sun in this world and no key light. Everything you can see is lit
   by something standing in the street with it: sodium on brackets, neon bolted to
   a frontage, a lit shopfront, a window four storeys up, a pair of headlights.
   The road is the second half of the lighting model — wet, it mirrors all of them
   back at you, and the four named states move that model rather than the palette:
   how much water is on the ground, how hard it is raining, how far the halo around
   each source opens, and how many of the sources are switched on at all.
   ═══════════════════════════════════════════════════════════════════════ */

const STATES = {
  'dry-dusk': {
    caption: 'The last of the daylight is still in the cloud, the tarmac is dry, and the signs are only just starting to win.',
    murkC: [0.13, 0.15, 0.21], murkD: 0.0070, glowC: [0.21, 0.25, 0.36], glowI: 0.95,
    neonC: [0.9, 0.6, 0.7], neonI: 0.85, lampI: 0.55, signI: 0.60, carI: 0.7,
    winC: [1.0, 0.82, 0.55], winI: 0.85, winOcc: 0.30,
    tarC: [0.105, 0.105, 0.118], grime: 0.55,
    wet: 0.10, ripple: 0.15, rain: 0.0, halo: 0.20, star: 0.0,
    gustX: 0.10, gustZ: 0.05, bloom: 0.26, exposure: 0.92 },
  'neon-rain': {
    caption: 'Hard rain. Every sign in the street is standing upside down in the road, and the road will not hold still.',
    murkC: [0.085, 0.065, 0.105], murkD: 0.0125, glowC: [0.16, 0.13, 0.22], glowI: 0.62,
    neonC: [1.0, 0.25, 0.55], neonI: 1.25, lampI: 0.80, signI: 1.75, carI: 1.10,
    winC: [1.0, 0.80, 0.52], winI: 1.00, winOcc: 0.46,
    tarC: [0.060, 0.060, 0.074], grime: 0.35,
    wet: 1.00, ripple: 1.00, rain: 1.00, halo: 0.75, star: 0.0,
    gustX: 0.55, gustZ: 0.30, bloom: 0.46, exposure: 0.90 },
  'after-midnight': {
    caption: 'The shops are shut and the flats are dark. Only the sodium is left, and the street has gone to a black mirror under it.',
    murkC: [0.045, 0.048, 0.072], murkD: 0.0085, glowC: [0.085, 0.100, 0.170], glowI: 0.62,
    neonC: [0.55, 0.65, 1.0], neonI: 1.05, lampI: 1.35, signI: 0.35, carI: 0.9,
    winC: [1.0, 0.76, 0.45], winI: 0.85, winOcc: 0.07,
    tarC: [0.055, 0.055, 0.068], grime: 0.45,
    wet: 0.85, ripple: 0.35, rain: 0.15, halo: 0.35, star: 0.35,
    gustX: 0.12, gustZ: 0.06, bloom: 0.40, exposure: 0.95 },
  'fog-halo': {
    caption: 'Fog off the river. Nothing has an edge any more — every light in the street is just the middle of its own halo.',
    murkC: [0.22, 0.175, 0.145], murkD: 0.0290, glowC: [0.26, 0.21, 0.165], glowI: 0.70,
    neonC: [1.0, 0.70, 0.35], neonI: 1.15, lampI: 1.45, signI: 1.05, carI: 1.0,
    winC: [1.0, 0.80, 0.50], winI: 0.90, winOcc: 0.22,
    tarC: [0.075, 0.073, 0.080], grime: 0.50,
    wet: 0.70, ripple: 0.30, rain: 0.25, halo: 1.55, star: 0.0,
    gustX: 0.06, gustZ: 0.03, bloom: 0.62, exposure: 0.95 },
};
const ORDER = Object.keys(STATES);
const isColor = (k) => Array.isArray(STATES[ORDER[0]][k]);

const sceneDef = {
  meta: { fov: 64, near: 0.08, far: 900, pixelRatio: 1.5, rate: 1.1, seed: 7, toneMapping: 'ACESFilmicToneMapping' },

  buildUniforms() {
    return {
      uTime: F(0),
      // the emitter array: this world's replacement for a sun. Downpour rewrites it
      // every frame from the fixtures nearest the camera.
      uEmiP: { value: Array.from({ length: NLAMP }, () => new THREE.Vector3(0, -50, 0)) },
      uEmiC: { value: Array.from({ length: NLAMP }, () => new THREE.Color(1, 1, 1)) },
      uEmiI: { value: new Array(NLAMP).fill(0) },
      uMurkC: C3(), uMurkD: F(0.012),
      uGlowC: C3(), uGlowI: F(0.6),
      uNeonC: C3(), uNeonI: F(1), uLampI: F(1), uSignI: F(1),
      uWinC: C3(), uWinI: F(1), uWinOcc: F(0.3),
      uTarC: C3(), uGrime: F(0.5),
      uWetness: F(0.5), uRipple: F(0.5), uRainAmt: F(0.5), uHaloR: F(0.4), uStarI: F(0),
      uKerbX: F(KERB_X), uFaceX: F(FACE_X),
      uGust: { value: new THREE.Vector2(0.2, 0.1) },
    };
  },

  initialState() { const h = location.hash.slice(1); return STATES[h] ? h : ORDER[0]; },

  resolveState(name) {
    const s = STATES[STATES[name] ? name : ORDER[0]];
    const t = {};
    for (const k in s) { if (k === 'caption') continue; t[k] = isColor(k) ? new THREE.Color(...s[k]) : s[k]; }
    return t;
  },

  applyToUniforms(cur, ctx) {
    const U = ctx.U;
    U.uMurkC.value.copy(cur.murkC); U.uMurkD.value = cur.murkD;
    U.uGlowC.value.copy(cur.glowC); U.uGlowI.value = cur.glowI;
    U.uNeonC.value.copy(cur.neonC); U.uNeonI.value = cur.neonI;
    U.uLampI.value = cur.lampI; U.uSignI.value = cur.signI;
    U.uWinC.value.copy(cur.winC); U.uWinI.value = cur.winI; U.uWinOcc.value = cur.winOcc;
    U.uTarC.value.copy(cur.tarC); U.uGrime.value = cur.grime;
    U.uWetness.value = cur.wet; U.uRipple.value = cur.ripple; U.uRainAmt.value = cur.rain;
    U.uHaloR.value = cur.halo; U.uStarI.value = cur.star;
    U.uGust.value.set(cur.gustX, cur.gustZ);
  },

  setup(ctx) { ctx.scene.background = ctx.U.uMurkC.value; },

  layers: [Overcast, Blacktop, Kerbside, Passersby, Downpour],
  camera: CameraRig,
  postfx: PostFX,

  onHashChange(sm) { const name = STATES[location.hash.slice(1)] ? location.hash.slice(1) : ORDER[0]; sm.setState(name); showState(name); },

  setupUI(ctx, sm) {
    captionEl = document.getElementById('caption'); nav = document.getElementById('nav');
    ORDER.forEach((n) => { const b = document.createElement('button'); b.textContent = n; b.dataset.state = n; b.addEventListener('click', () => { location.hash = n; }); nav.appendChild(b); });
    showState(sceneDef.initialState(), true);
  },
};

// ---- caption + nav (module-scoped, wired in setupUI) ----
let captionEl, nav;
function showState(name, instant = false) {
  nav.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.state === name));
  captionEl.classList.add('fade');
  setTimeout(() => { captionEl.textContent = STATES[name].caption; captionEl.classList.remove('fade'); }, instant ? 0 : 500);
}

boot(document.getElementById('scene'), sceneDef);
