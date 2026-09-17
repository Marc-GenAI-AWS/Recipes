import * as THREE from 'three';
import { boot, F, C3, V3 } from '../contract/runtime.js';
import { HALO_Y, HOLE_R, HOLE_Y } from './field.js';
import { Cavern } from './layers/cavern.js';
import { Skylight } from './layers/skylight.js';
import { Surface } from './layers/surface.js';
import { Halocline } from './layers/halocline.js';
import { Reef } from './layers/reef.js';
import { Fish } from './layers/fish.js';
import { Bubbles } from './layers/bubbles.js';
import { Motes } from './layers/motes.js';
import { CameraRig } from './camera.js';
import { PostFX } from './postfx.js';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE: Cenote — a shaft of light in a flooded sinkhole.
   Enumerated manifest (SCENE_CONTRACT §8): four named states.
   ═══════════════════════════════════════════════════════════════════════ */

const STATES = {
  'morning-beam': {
    caption: 'First light finds the mouth of the cenote and enters at a slant — a single gold blade laid across the reef.',
    fogTop: [0.02, 0.13, 0.17], fogDeep: [0.015, 0.11, 0.15], fogDT: 0.024, fogDD: 0.03, sunC: [1.0, 0.68, 0.36], sunI: 1.3, beamI: 1.1, tilt: 0.48,
    ambC: [0.12, 0.26, 0.26], ambI: 0.3, caus: 0.8, halo: 0.35, rain: 0.0, ripple: 0.5, fishSpeed: 0.8, fishFrac: 1.0, bubbles: 0.6,
    partA: 0.55, partC: [0.95, 0.85, 0.65], coralSat: 0.85, coralGlow: 0.1, torch: 0.0, bloom: 0.25, exposure: 0.95, sky: [0.85, 0.72, 0.50], skyGlow: 1.3, moon: 0.0 },
  'noon-pillar': {
    caption: 'At noon the sun stands over the opening and the beam becomes a pillar, white to the seabed, fish flashing silver as they cross it.',
    fogTop: [0.02, 0.23, 0.32], fogDeep: [0.02, 0.19, 0.27], fogDT: 0.02, fogDD: 0.028, sunC: [1.0, 1.0, 0.94], sunI: 1.7, beamI: 1.3, tilt: 0.0,
    ambC: [0.12, 0.42, 0.45], ambI: 0.45, caus: 1.2, halo: 0.30, rain: 0.0, ripple: 0.4, fishSpeed: 1.1, fishFrac: 1.0, bubbles: 0.9,
    partA: 0.45, partC: [1.0, 1.0, 0.95], coralSat: 1.0, coralGlow: 0.1, torch: 0.0, bloom: 0.3, exposure: 0.95, sky: [0.55, 0.80, 1.0], skyGlow: 1.8, moon: 0.0 },
  'storm-runoff': {
    caption: 'Last night’s rain: the upper water runs tea-brown with tannin, the halocline pools over the coral, and the light gives up a few metres down.',
    fogTop: [0.11, 0.07, 0.025], fogDeep: [0.03, 0.07, 0.10], fogDT: 0.036, fogDD: 0.035, sunC: [0.95, 0.75, 0.45], sunI: 0.7, beamI: 0.6, tilt: 0.1,
    ambC: [0.22, 0.15, 0.07], ambI: 0.35, caus: 0.25, halo: 0.6, rain: 1.0, ripple: 1.1, fishSpeed: 0.45, fishFrac: 0.7, bubbles: 0.3,
    partA: 0.8, partC: [0.75, 0.55, 0.3], coralSat: 0.5, coralGlow: 0.1, torch: 0.0, bloom: 0.2, exposure: 1.0, sky: [0.46, 0.46, 0.42], skyGlow: 0.35, moon: 0.0 },
  'night-torch': {
    caption: 'Night. The hole above is a coin of stars; a diver’s torch swings across the reef and the corals fluoresce back.',
    fogTop: [0.006, 0.02, 0.04], fogDeep: [0.003, 0.012, 0.025], fogDT: 0.03, fogDD: 0.045, sunC: [0.5, 0.62, 0.9], sunI: 0.18, beamI: 0.14, tilt: 0.15,
    ambC: [0.02, 0.05, 0.09], ambI: 0.28, caus: 0.1, halo: 0.25, rain: 0.0, ripple: 0.3, fishSpeed: 0.35, fishFrac: 0.4, bubbles: 0.2,
    partA: 0.5, partC: [0.8, 0.86, 1.0], coralSat: 0.45, coralGlow: 1.0, torch: 3.2, bloom: 0.7, exposure: 1.0, sky: [0.02, 0.04, 0.10], skyGlow: 0.25, moon: 1.0 },
};
const ORDER = Object.keys(STATES);
const isColor = (k) => Array.isArray(STATES[ORDER[0]][k]);

const sceneDef = {
  meta: { fov: 56, near: 0.1, far: 140, pixelRatio: 1.5, rate: 1.1, seed: 7, toneMapping: 'ACESFilmicToneMapping' },

  buildUniforms() {
    return {
      uTime: F(0), uFogTop: C3(), uFogDeep: C3(), uFogDT: F(0.04), uFogDD: F(0.06), uHaloY: F(HALO_Y), uHalo: F(0.3),
      uSunDir: V3(0, -1, 0), uSunC: C3(), uSunI: F(1), uAmbC: C3(), uAmbI: F(0.5), uCaus: F(1),
      uBeamTop: V3(0, 0, 0), uBeamDir: V3(0, -1, 0), uBeamR: F(HOLE_R * 1.02), uBeamI: F(1),
      uTorchPos: V3(), uTorchDir: V3(0, 0, -1), uTorchI: F(0), uHolePos: V3(0, HOLE_Y, 0), uRain: F(0), uRipple: F(0.5),
      uSky: C3(), uSkyGlow: F(1), uMoon: F(0), uSat: F(1), uGlow: F(0), uSunOff: { value: new THREE.Vector2() }, uPartA: F(0.5), uPartC: C3(), uFishSpeed: F(1),
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
    U.uFogTop.value.copy(cur.fogTop); U.uFogDeep.value.copy(cur.fogDeep); U.uFogDT.value = cur.fogDT; U.uFogDD.value = cur.fogDD;
    U.uSunC.value.copy(cur.sunC); U.uSunI.value = cur.sunI; U.uAmbC.value.copy(cur.ambC); U.uAmbI.value = cur.ambI; U.uCaus.value = cur.caus;
    U.uBeamI.value = cur.beamI; U.uHalo.value = cur.halo; U.uRain.value = cur.rain; U.uRipple.value = cur.ripple; U.uTorchI.value = cur.torch;
    U.uSky.value.copy(cur.sky); U.uSkyGlow.value = cur.skyGlow; U.uMoon.value = cur.moon; U.uPartA.value = cur.partA; U.uPartC.value.copy(cur.partC); U.uFishSpeed.value = cur.fishSpeed; U.uSat.value = cur.coralSat; U.uGlow.value = cur.coralGlow;
    U.uBeamDir.value.set(Math.sin(cur.tilt), -Math.cos(cur.tilt), 0); U.uSunDir.value.copy(U.uBeamDir.value); U.uSunOff.value.set(-Math.sin(cur.tilt) * 0.9, 0.0);
  },

  setup(ctx) { ctx.scene.background = ctx.U.uFogTop.value; },

  layers: [Cavern, Skylight, Surface, Halocline, Reef, Fish, Bubbles, Motes],
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
