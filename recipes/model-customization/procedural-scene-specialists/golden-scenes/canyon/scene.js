import * as THREE from 'three';
import { boot, F, C3, V3 } from '../contract/runtime.js';
import { RIM } from './field.js';
import { Walls } from './layers/walls.js';
import { Firmament } from './layers/firmament.js';
import { Scrub } from './layers/scrub.js';
import { Raptors } from './layers/raptors.js';
import { Dust } from './layers/dust.js';
import { CameraRig } from './camera.js';
import { PostFX } from './postfx.js';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE: Canyon — a slot canyon in a desert mesa under hard light.
   Enumerated manifest: four named states, chosen to move the LIGHTING MODEL
   and not merely the palette — direct sun down the slot, bounce off the walls,
   dust scattering, and a night with no sun at all.
   ═══════════════════════════════════════════════════════════════════════ */

const STATES = {
  'dawn-rim': {
    caption: 'First sun catches only the rim; the floor is still holding last night’s blue, and the walls glow from the top down.',
    hazeC: [0.44, 0.38, 0.40], hazeD: 0.0075, skyC: [0.42, 0.52, 0.78], skyI: 0.85,
    sunC: [1.0, 0.62, 0.34], sunI: 0.9, sunEl: 0.13, sunAz: 0.95,
    bounceC: [0.85, 0.45, 0.26], bounceI: 0.22, dust: 0.12, shimmer: 0.0, strata: 0.85,
    rockC: [0.60, 0.33, 0.22], windX: 0.10, windZ: 0.04, scrubDry: 0.35, birdSpeed: 0.6,
    moon: 0.15, stars: 0.18, bloom: 0.28, exposure: 1.0 },
  'high-noon': {
    caption: 'The sun stands in the slot. Light goes straight to the floor, the walls throw it back at each other, and everything is edge and glare.',
    hazeC: [0.72, 0.62, 0.52], hazeD: 0.0055, skyC: [0.30, 0.52, 0.92], skyI: 1.35,
    sunC: [1.0, 0.97, 0.90], sunI: 2.0, sunEl: 1.32, sunAz: 0.2,
    bounceC: [0.95, 0.55, 0.32], bounceI: 0.75, dust: 0.18, shimmer: 0.8, strata: 1.0,
    rockC: [0.68, 0.38, 0.25], windX: 0.18, windZ: 0.05, scrubDry: 0.55, birdSpeed: 1.0,
    moon: 0.0, stars: 0.0, bloom: 0.34, exposure: 0.92 },
  'dust-storm': {
    caption: 'Wind funnels down the corridor and fills it with ochre; the far wall goes to a rumour and the sun to a coin.',
    hazeC: [0.66, 0.45, 0.26], hazeD: 0.019, skyC: [0.62, 0.48, 0.30], skyI: 0.75,
    sunC: [0.95, 0.66, 0.36], sunI: 0.85, sunEl: 0.85, sunAz: -0.5,
    bounceC: [0.72, 0.42, 0.24], bounceI: 0.30, dust: 1.0, shimmer: 0.25, strata: 0.5,
    rockC: [0.58, 0.35, 0.24], windX: 0.85, windZ: 0.35, scrubDry: 0.8, birdSpeed: 0.35,
    moon: 0.0, stars: 0.0, bloom: 0.18, exposure: 1.05 },
  'night-cold': {
    caption: 'No sun at all. The rock gives back the day’s heat to a sky full of stars, and the canyon reads in silhouette.',
    hazeC: [0.05, 0.07, 0.12], hazeD: 0.010, skyC: [0.10, 0.16, 0.34], skyI: 0.42,
    sunC: [0.40, 0.52, 0.85], sunI: 0.10, sunEl: -0.35, sunAz: 2.1,
    bounceC: [0.18, 0.22, 0.38], bounceI: 0.10, dust: 0.08, shimmer: 0.0, strata: 0.6,
    rockC: [0.40, 0.28, 0.24], windX: 0.06, windZ: 0.02, scrubDry: 0.45, birdSpeed: 0.2,
    moon: 1.0, stars: 1.0, bloom: 0.55, exposure: 1.08 },
};
const ORDER = Object.keys(STATES);
const isColor = (k) => Array.isArray(STATES[ORDER[0]][k]);

const sceneDef = {
  meta: { fov: 62, near: 0.1, far: 700, pixelRatio: 1.5, rate: 1.1, seed: 7, toneMapping: 'ACESFilmicToneMapping' },

  buildUniforms() {
    return {
      uTime: F(0),
      uHazeC: C3(), uHazeD: F(0.008),
      uSkyC: C3(), uSkyI: F(1),
      uSunDir: V3(0, -1, 0), uSunC: C3(), uSunI: F(1),
      uBounceC: C3(), uBounceI: F(0.4),
      uDust: F(0.2), uShimmer: F(0), uStrata: F(1), uMoon: F(0), uStars: F(0),
      uRockC: C3(), uDry: F(0.5), uRimY: F(RIM),
      uWind: { value: new THREE.Vector2(0.15, 0.05) },
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
    U.uHazeC.value.copy(cur.hazeC); U.uHazeD.value = cur.hazeD;
    U.uSkyC.value.copy(cur.skyC); U.uSkyI.value = cur.skyI;
    U.uSunC.value.copy(cur.sunC); U.uSunI.value = cur.sunI;
    U.uBounceC.value.copy(cur.bounceC); U.uBounceI.value = cur.bounceI;
    U.uDust.value = cur.dust; U.uShimmer.value = cur.shimmer; U.uStrata.value = cur.strata;
    U.uMoon.value = cur.moon; U.uStars.value = cur.stars;
    U.uRockC.value.copy(cur.rockC); U.uDry.value = cur.scrubDry;
    U.uWind.value.set(cur.windX, cur.windZ);
    // sun direction from elevation/azimuth: this is the vector layers shade against
    const ce = Math.cos(cur.sunEl);
    U.uSunDir.value.set(-ce * Math.sin(cur.sunAz), -Math.sin(cur.sunEl), -ce * Math.cos(cur.sunAz)).normalize();
  },

  setup(ctx) { ctx.scene.background = ctx.U.uHazeC.value; },

  layers: [Walls, Firmament, Scrub, Raptors, Dust],
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
