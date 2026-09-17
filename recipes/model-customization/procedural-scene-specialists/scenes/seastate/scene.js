import * as THREE from 'three';
import { boot, F, C3, V3 } from '../contract/runtime.js';
import { computeTarget, forecastLine } from './presets.js';
import { Sky } from './layers/sky.js';
import { Ocean } from './layers/ocean.js';
import { Rain } from './layers/rain.js';
import { CameraRig } from './camera.js';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE: Sea State — an open ocean seen from a ship's bow.
   Factored manifest (SCENE_CONTRACT.md §8): state = "<time>-<weather>".
   Layers: Sky (dome + clouds) · Ocean (Gerstner water) · Rain (+lightning).
   ═══════════════════════════════════════════════════════════════════════ */

const TIME_SET = { dawn: 1, midday: 1, dusk: 1, night: 1 };
const WX_SET = { clear: 1, cloudy: 1, fog: 1, rain: 1, storm: 1 };
let timeKey = 'dusk';
let wxKey = 'clear';

function parseHash(hash) {
  const m = (hash || '').replace('#', '').split('-');
  const tk = m[0] in TIME_SET ? m[0] : 'dusk';
  const wk = m[1] in WX_SET ? m[1] : 'clear';
  return [tk, wk];
}

const sceneDef = {
  meta: { fov: 55, near: 0.5, far: 10000, pixelRatio: 2, rate: 1.4, seed: 7 },

  buildUniforms() {
    return {
      uSunDir: V3(0, 1, 0), uSunTint: C3(), uZenith: C3(), uHorizon: C3(),
      uGradFalloff: F(0.6), uSunDisc: F(1), uSunGlow: F(1),
      uCloudCoverage: F(0.1), uCloudDensity: F(0.6), uCloudScale: F(1.1),
      uCloudOff: { value: new THREE.Vector2(0, 0) }, uCloudLit: C3(), uCloudShadow: C3(),
      uFogColor: C3(), uFogVeil: F(0.05), uStars: F(0),
      uMoonDir: V3(0, 1, 0), uMoon: F(0), uLightning: F(0), uTime: F(0), uExposure: F(1),
    };
  },

  initialState() {
    [timeKey, wxKey] = parseHash(location.hash);
    return `${timeKey}-${wxKey}`;
  },

  resolveState(name) {
    const [tk, wk] = parseHash('#' + name);
    return computeTarget(tk, wk);
  },

  // publish the shared palette every material reads (the sky-owned channels)
  applyToUniforms(cur, ctx) {
    const U = ctx.U;
    U.uSunDir.value.copy(cur.sunDir).normalize();
    U.uSunTint.value.copy(cur.sunTint);
    U.uZenith.value.copy(cur.zenith);
    U.uHorizon.value.copy(cur.horizon);
    U.uGradFalloff.value = cur.gradFalloff;
    U.uSunDisc.value = cur.sunDisc;
    U.uSunGlow.value = cur.sunGlow;
    U.uCloudCoverage.value = cur.cloudCoverage;
    U.uCloudDensity.value = cur.cloudDensity;
    U.uCloudScale.value = cur.cloudScale;
    U.uCloudLit.value.copy(cur.cloudLit);
    U.uCloudShadow.value.copy(cur.cloudShadow);
    U.uFogColor.value.copy(cur.fogColor);
    U.uFogVeil.value = cur.fogVeil;
    U.uStars.value = cur.stars;
    U.uMoonDir.value.copy(cur.moonDir).normalize();
    U.uMoon.value = cur.moon;
    U.uExposure.value = cur.exposure;
  },

  layers: [Sky, Ocean, Rain],
  camera: CameraRig,

  onHashChange(sm) {
    [timeKey, wxKey] = parseHash(location.hash);
    sm.setState(`${timeKey}-${wxKey}`);
    syncButtons();
    setForecast();
  },

  setupUI(ctx, sm) {
    _sm = sm;
    ui = document.getElementById('ui');
    forecastEl = document.getElementById('forecast');
    timeButtons = [...document.querySelectorAll('[data-time]')];
    wxButtons = [...document.querySelectorAll('[data-weather]')];

    timeButtons.forEach((b) => b.addEventListener('click', () => select(b.dataset.time, null)));
    wxButtons.forEach((b) => b.addEventListener('click', () => select(null, b.dataset.weather)));

    addEventListener('keydown', (ev) => {
      if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const k = ev.key.toLowerCase();
      if (KEY_TIME[k]) select(KEY_TIME[k], null);
      else if (KEY_WX[k]) select(null, KEY_WX[k]);
      else if (k === 'h') ui.classList.toggle('hidden');
    });

    syncButtons();
    forecastEl.textContent = forecastLine(timeKey, wxKey);
  },
};

// ---- UI state (module-scoped, wired in setupUI) ----
let _sm, ui, forecastEl, timeButtons = [], wxButtons = [];
const KEY_TIME = { 1: 'dawn', 2: 'midday', 3: 'dusk', 4: 'night' };
const KEY_WX = { q: 'clear', w: 'cloudy', e: 'fog', r: 'rain', t: 'storm' };

function syncButtons() {
  timeButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.time === timeKey)));
  wxButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.weather === wxKey)));
}
function setForecast() {
  forecastEl.classList.add('fading');
  setTimeout(() => {
    forecastEl.textContent = forecastLine(timeKey, wxKey);
    forecastEl.classList.remove('fading');
  }, 300);
}
function select(newTime, newWx) {
  if (newTime) timeKey = newTime;
  if (newWx) wxKey = newWx;
  _sm.setState(`${timeKey}-${wxKey}`);
  syncButtons();
  history.replaceState(null, '', `#${timeKey}-${wxKey}`);
  setForecast();
}

boot(document.getElementById('scene'), sceneDef);
