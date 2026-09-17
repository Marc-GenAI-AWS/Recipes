import * as THREE from 'three';
import { boot, F, C3, V3 } from '../contract/runtime.js';
import { EDGE, CREST } from './field.js';
import { Icefield } from './layers/icefield.js';
import { Aether } from './layers/aether.js';
import { Lichen } from './layers/lichen.js';
import { Ravens } from './layers/ravens.js';
import { Spindrift } from './layers/spindrift.js';
import { CameraRig } from './camera.js';
import { PostFX } from './postfx.js';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE: Glacier — a high alpine basin under an inverted exposure range.
   Everything here is bright and the contrast is low: snow throws light back UP
   into every shadow, and the ice is translucent, so shadows go blue and filled
   rather than black. Enumerated manifest: four named states, chosen to move the
   LIGHTING MODEL and not merely the palette — the ratio of direct sun to sky
   dome to upwash, how deep light travels into the ice, and how much of the
   direction is left in the light at all.
   ═══════════════════════════════════════════════════════════════════════ */

const STATES = {
  'blue-dawn': {
    caption: 'The sun has not cleared the headwall. Every photon in the basin has come off the sky, so the snow is the colour of the sky — and the crevasses, lit from inside by nothing, are the only warm thing left.',
    airC: [0.62, 0.72, 0.92], airD: 0.0026, zenithC: [0.06, 0.15, 0.44],
    domeC: [0.50, 0.66, 1.00], domeI: 0.30, upwashC: [0.52, 0.68, 1.00], upwashI: 0.26,
    solarC: [0.62, 0.72, 1.00], solarI: 0.10, solarEl: -0.055, solarAz: 2.42,
    snowC: [0.84, 0.90, 1.00], iceC: [0.16, 0.48, 0.92], moraineC: [0.30, 0.31, 0.36],
    iceDepth: 0.34, glare: 0.15, whiteout: 0.04, glint: 0.18, crevasse: 1.0, drift: 0.16,
    halo: 0.0, alpen: 0.06, lichenD: 0.30, gustX: 0.05, gustZ: 0.16, ravenSpeed: 0.45,
    bloom: 0.20, exposure: 0.92 },
  'white-noon': {
    caption: 'Noon at three and a half thousand metres. The sun is a hole in the sky, the snow gives most of it straight back up, and there is nowhere in the basin dark enough to rest your eye.',
    airC: [0.88, 0.93, 1.00], airD: 0.0021, zenithC: [0.05, 0.16, 0.52],
    domeC: [0.72, 0.84, 1.00], domeI: 0.24, upwashC: [0.90, 0.95, 1.00], upwashI: 0.30,
    solarC: [1.00, 0.985, 0.95], solarI: 0.84, solarEl: 0.58, solarAz: 2.50,
    snowC: [0.96, 0.97, 1.00], iceC: [0.20, 0.60, 1.00], moraineC: [0.36, 0.35, 0.37],
    iceDepth: 0.52, glare: 1.00, whiteout: 0.0, glint: 1.00, crevasse: 1.0, drift: 0.30,
    halo: 0.30, alpen: 0.0, lichenD: 0.55, gustX: 0.10, gustZ: 0.30, ravenSpeed: 1.0,
    bloom: 0.40, exposure: 0.74 },
  'whiteout': {
    caption: 'Cloud has come up the valley and filled the basin. The light arrives from every direction at once, which is the same as arriving from none: the surface loses its shadows, and with them any way of telling a step from a hole.',
    airC: [0.84, 0.88, 0.93], airD: 0.0062, zenithC: [0.66, 0.72, 0.82],
    domeC: [0.90, 0.94, 1.00], domeI: 0.34, upwashC: [0.92, 0.95, 1.00], upwashI: 0.26,
    solarC: [0.94, 0.95, 0.97], solarI: 0.30, solarEl: 0.78, solarAz: 1.55,
    snowC: [0.94, 0.95, 0.98], iceC: [0.42, 0.62, 0.86], moraineC: [0.42, 0.42, 0.44],
    iceDepth: 0.20, glare: 0.10, whiteout: 0.88, glint: 0.08, crevasse: 0.55, drift: 1.00,
    halo: 0.0, alpen: 0.0, lichenD: 0.70, gustX: 0.55, gustZ: 0.85, ravenSpeed: 0.7,
    bloom: 0.26, exposure: 0.70 },
  'alpenglow': {
    caption: 'The last sun comes in almost level, red, and grazing. The snow takes the red and the shadows keep the sky, so the whole basin splits into two colours and a halo stands up around the sun.',
    airC: [0.94, 0.66, 0.58], airD: 0.0034, zenithC: [0.08, 0.14, 0.40],
    domeC: [0.42, 0.56, 0.96], domeI: 0.30, upwashC: [0.98, 0.72, 0.66], upwashI: 0.28,
    solarC: [1.00, 0.52, 0.36], solarI: 0.90, solarEl: 0.075, solarAz: 2.62,
    snowC: [0.96, 0.92, 0.94], iceC: [0.22, 0.52, 0.98], moraineC: [0.40, 0.31, 0.29],
    iceDepth: 0.46, glare: 0.62, whiteout: 0.02, glint: 0.55, crevasse: 1.0, drift: 0.22,
    halo: 0.85, alpen: 1.00, lichenD: 0.40, gustX: 0.06, gustZ: 0.20, ravenSpeed: 0.6,
    bloom: 0.50, exposure: 0.88 },
};
const ORDER = Object.keys(STATES);
const isColor = (k) => Array.isArray(STATES[ORDER[0]][k]);

const sceneDef = {
  meta: { fov: 58, near: 0.1, far: 1600, pixelRatio: 1.5, rate: 1.1, seed: 11, toneMapping: 'ACESFilmicToneMapping' },

  buildUniforms() {
    return {
      uTime: F(0),
      uAirC: C3(), uAirD: F(0.003),
      uZenithC: C3(), uDomeC: C3(), uDomeI: F(0.3),
      uSolarV: V3(0, -1, 0), uSolarC: C3(), uSolarI: F(0.5),
      uUpwashC: C3(), uUpwashI: F(0.28),
      uSnowC: C3(), uIceC: C3(), uMoraineC: C3(),
      uIceDepth: F(0.4), uGlareI: F(0.6), uWhiteout: F(0), uGlintI: F(0.6),
      uCrevasse: F(1), uDrift: F(0.3), uHaloI: F(0), uAlpenI: F(0), uLichenD: F(0.5),
      uEdgeX: F(EDGE), uCrestY: F(CREST),
      uGustV: { value: new THREE.Vector2(0.1, 0.3) },
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
    U.uAirC.value.copy(cur.airC); U.uAirD.value = cur.airD;
    U.uZenithC.value.copy(cur.zenithC);
    U.uDomeC.value.copy(cur.domeC); U.uDomeI.value = cur.domeI;
    U.uSolarC.value.copy(cur.solarC); U.uSolarI.value = cur.solarI;
    U.uUpwashC.value.copy(cur.upwashC); U.uUpwashI.value = cur.upwashI;
    U.uSnowC.value.copy(cur.snowC); U.uIceC.value.copy(cur.iceC); U.uMoraineC.value.copy(cur.moraineC);
    U.uIceDepth.value = cur.iceDepth; U.uGlareI.value = cur.glare; U.uWhiteout.value = cur.whiteout;
    U.uGlintI.value = cur.glint; U.uCrevasse.value = cur.crevasse; U.uDrift.value = cur.drift;
    U.uHaloI.value = cur.halo; U.uAlpenI.value = cur.alpen; U.uLichenD.value = cur.lichenD;
    U.uGustV.value.set(cur.gustX, cur.gustZ);
    // sun direction from elevation/azimuth: this is the vector every layer shades against
    const ce = Math.cos(cur.solarEl);
    U.uSolarV.value.set(-ce * Math.sin(cur.solarAz), -Math.sin(cur.solarEl), -ce * Math.cos(cur.solarAz)).normalize();
  },

  setup(ctx) { ctx.scene.background = ctx.U.uAirC.value; },

  layers: [Aether, Icefield, Lichen, Ravens, Spindrift],
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
