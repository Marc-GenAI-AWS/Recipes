import * as THREE from 'three';
import { boot, F, C3, V3 } from '../contract/runtime.js';
import { SADDLE } from './field.js';
import { Atmosphere } from './layers/atmosphere.js';
import { Peaks } from './layers/peaks.js';
import { Prairie } from './layers/prairie.js';
import { Grass } from './layers/grass.js';
import { Outcrops } from './layers/outcrops.js';
import { Mist } from './layers/mist.js';
import { Shafts } from './layers/shafts.js';
import { Herd } from './layers/herd.js';
import { AirLife } from './layers/airlife.js';
import { Fluff } from './layers/fluff.js';
import { Rain } from './layers/rain.js';
import { Lightning } from './layers/lightning.js';
import { CameraRig } from './camera.js';
import { PostFX } from './postfx.js';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE: High Park — a prairie basin under the peaks.
   Enumerated manifest (SCENE_CONTRACT §8): four named states; default is the
   second (cloud-shadows). Rain + lightning gate to storm-break only.
   ═══════════════════════════════════════════════════════════════════════ */

const STATES = {
  'first-light': {
    caption: 'Dawn. The summits take the first pink light while the basin waits in blue shadow, mist lying along the creek hollows.',
    skyTop: [0.22, 0.30, 0.52], skyHorizon: [0.95, 0.68, 0.50], sunC: [1.0, 0.70, 0.45], sunI: 0.85, sunEl: 0.10,
    peakSnow: [1.0, 0.78, 0.72], peakRock: [0.30, 0.26, 0.28], grassA: [0.16, 0.20, 0.12], grassB: [0.55, 0.48, 0.30],
    fog: [0.66, 0.60, 0.62], fogD: 0.0016, wind: 0.30, cloud: 0.25, shadowAmt: 0.25, shaft: 0.75, shaftTilt: 0.42,
    rain: 0.0, mist: 1.0, herdMood: 0.12, herdSpeed: 0.35, fluff: 0.35, hawk: 0.4, stars: 0.12, bloom: 0.35, exposure: 1.0 },
  'cloud-shadows': {
    caption: 'Mid-morning wind. Cumulus shadows race each other across the park, and the herd grazes through light and dark without looking up.',
    skyTop: [0.24, 0.48, 0.86], skyHorizon: [0.76, 0.85, 0.92], sunC: [1.0, 0.98, 0.92], sunI: 1.45, sunEl: 0.75,
    peakSnow: [0.97, 0.98, 1.0], peakRock: [0.38, 0.36, 0.34], grassA: [0.15, 0.26, 0.10], grassB: [0.62, 0.60, 0.26],
    fog: [0.74, 0.82, 0.90], fogD: 0.0008, wind: 1.0, cloud: 0.6, shadowAmt: 1.0, shaft: 0.18, shaftTilt: 0.05,
    rain: 0.0, mist: 0.0, herdMood: 0.25, herdSpeed: 0.7, fluff: 1.0, hawk: 1.0, stars: 0.0, bloom: 0.22, exposure: 1.08 },
  'storm-break': {
    caption: 'A shelf of storm shuts the sky — then splits at the saddle, and one great blade of sun walks across the basin. The horses run ahead of it.',
    skyTop: [0.20, 0.22, 0.28], skyHorizon: [0.48, 0.46, 0.44], sunC: [1.0, 0.88, 0.62], sunI: 0.95, sunEl: 0.35,
    peakSnow: [0.72, 0.74, 0.80], peakRock: [0.20, 0.20, 0.23], grassA: [0.11, 0.17, 0.08], grassB: [0.44, 0.42, 0.20],
    fog: [0.44, 0.45, 0.48], fogD: 0.0019, wind: 2.1, cloud: 0.95, shadowAmt: 0.55, shaft: 1.6, shaftTilt: 0.22,
    rain: 1.0, mist: 0.15, herdMood: 1.0, herdSpeed: 1.6, fluff: 0.55, hawk: 0.0, stars: 0.0, bloom: 0.5, exposure: 0.98 },
  'gold-dusk': {
    caption: 'The sun goes down exactly in the gap. Long gold light combs the seed heads, the hawk drops home, and the herd stands quiet, ears loose.',
    skyTop: [0.20, 0.15, 0.36], skyHorizon: [1.0, 0.60, 0.30], sunC: [1.0, 0.62, 0.32], sunI: 1.15, sunEl: 0.05,
    peakSnow: [1.0, 0.66, 0.55], peakRock: [0.28, 0.19, 0.20], grassA: [0.20, 0.15, 0.08], grassB: [0.95, 0.62, 0.26],
    fog: [0.72, 0.48, 0.36], fogD: 0.0020, wind: 0.4, cloud: 0.35, shadowAmt: 0.3, shaft: 1.1, shaftTilt: 0.02,
    rain: 0.0, mist: 0.3, herdMood: 0.18, herdSpeed: 0.3, fluff: 0.7, hawk: 0.3, stars: 0.3, bloom: 0.5, exposure: 1.12 },
};
const ORDER = Object.keys(STATES);
const isColor = (k) => Array.isArray(STATES[ORDER[0]][k]);

const sceneDef = {
  meta: { fov: 48, near: 0.1, far: 1600, pixelRatio: 1.5, rate: 1.1, seed: 11, toneMapping: 'ACESFilmicToneMapping' },

  buildUniforms() {
    return {
      uTime: F(0), uSkyTop: C3(), uSkyHorizon: C3(), uSunC: C3(), uSunI: F(1), uSunDir: V3(0, 0.3, -1),
      uFogC: C3(), uFogD: F(0.003), uWind: F(0.5), uCloud: F(0.5), uShadowAmt: F(0.5),
      uShaft: F(0.5), uShaftDir: V3(0, -0.5, 0.86), uSaddle: V3(SADDLE.x, SADDLE.y, SADDLE.z),
      uGrassA: C3(), uGrassB: C3(), uMist: F(0), uStars: F(0), uFlash: F(0),
    };
  },

  initialState() { const h = location.hash.slice(1); return STATES[h] ? h : ORDER[1]; },

  resolveState(name) {
    const s = STATES[STATES[name] ? name : ORDER[1]];
    const t = {};
    for (const k in s) { if (k === 'caption') continue; t[k] = isColor(k) ? new THREE.Color(...s[k]) : s[k]; }
    return t;
  },

  applyToUniforms(cur, ctx) {
    const U = ctx.U;
    U.uSkyTop.value.copy(cur.skyTop); U.uSkyHorizon.value.copy(cur.skyHorizon); U.uSunC.value.copy(cur.sunC); U.uSunI.value = cur.sunI;
    U.uFogC.value.copy(cur.fog); U.uFogD.value = cur.fogD; U.uWind.value = cur.wind; U.uCloud.value = cur.cloud; U.uShadowAmt.value = cur.shadowAmt;
    U.uGrassA.value.copy(cur.grassA); U.uGrassB.value.copy(cur.grassB); U.uMist.value = cur.mist; U.uStars.value = cur.stars;
    /* the sun sits above the saddle; the shaft corridor leans with shaftTilt through the day */
    U.uSunDir.value.set(Math.sin(cur.shaftTilt) * 0.6, Math.max(cur.sunEl, 0.03), -0.9).normalize();
    U.uShaft.value = cur.shaft;
    U.uShaftDir.value.set(Math.sin(cur.shaftTilt), -0.80, 0.55).normalize();
  },

  layers: [Atmosphere, Peaks, Prairie, Grass, Outcrops, Mist, Shafts, Herd, AirLife, Fluff, Rain, Lightning],
  camera: CameraRig,
  postfx: PostFX,

  onHashChange(sm) { const name = STATES[location.hash.slice(1)] ? location.hash.slice(1) : ORDER[1]; sm.setState(name); showState(name); },

  setupUI(ctx, sm) {
    captionEl = document.getElementById('caption'); nav = document.getElementById('nav');
    ORDER.forEach((n) => { const b = document.createElement('button'); b.textContent = n; b.dataset.state = n; b.addEventListener('click', () => { location.hash = n; }); nav.appendChild(b); });
    showState(sceneDef.initialState(), true);
  },
};

// ---- caption + nav ----
let captionEl, nav;
function showState(name, instant = false) {
  nav.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.state === name));
  captionEl.classList.add('fade');
  setTimeout(() => { captionEl.textContent = STATES[name].caption; captionEl.classList.remove('fade'); }, instant ? 0 : 500);
}

boot(document.getElementById('scene'), sceneDef);
