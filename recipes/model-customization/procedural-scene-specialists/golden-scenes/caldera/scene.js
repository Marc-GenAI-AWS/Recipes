import * as THREE from 'three';
import { boot, F, C3, V3 } from '../contract/runtime.js';
import { BOWL, RIM } from './field.js';
import { Crust } from './layers/crust.js';
import { Vault } from './layers/vault.js';
import { Scorch } from './layers/scorch.js';
import { Skein } from './layers/skein.js';
import { Plumes } from './layers/plumes.js';
import { CameraRig } from './camera.js';
import { PostFX } from './postfx.js';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE: Caldera — an active volcanic caldera, ash and steam.

   The light comes from the GROUND. Glowing fissures in the crust are the only
   real source in the world; the sky is a lid of ash and the darkest thing in
   frame. So faces point DOWN toward the light, the caldera's shadow is cast
   upward onto its own wall, and every layer shades against fireLight() rather
   than against a sun.

   Enumerated manifest: four named states, each of which moves the LIGHTING MODEL
   and not merely the palette — how much the fissures are emitting, how far up
   their light reaches (uGlowH), how much of the medium scatters it back, and how
   much (if any) daylight the ash pall is letting through from above.
   ═══════════════════════════════════════════════════════════════════════ */

const STATES = {
  'dawn-ash': {
    caption: 'Grey morning leaks through the pall — the most light this sky will ever have, and still less than the ground is giving back.',
    ashC: [0.105, 0.088, 0.082], ashD: 0.0030, ashFall: 0.22,
    vaultC: [0.062, 0.064, 0.080], vaultI: 0.62,
    paleC: [0.56, 0.58, 0.66], paleI: 0.20, paleEl: 0.35, paleAz: 2.30,
    lavaC: [1.00, 0.42, 0.13], crackI: 0.95, crackW: 0.135, fireI: 2.1, glowH: 17,
    crustC: [1.00, 0.95, 0.92], sulphC: [0.66, 0.58, 0.20],
    warp: 0.50, steamI: 1.00, sparkI: 0.70, scorch: 0.50, starI: 0.0,
    gustX: 0.10, gustZ: 0.05, birdRate: 0.9, bloom: 0.40, exposure: 1.00 },
  'fissure-open': {
    caption: 'A seam rips open across the pan. Everything in the caldera is suddenly lit from underneath, and the sky goes to nothing by comparison.',
    ashC: [0.135, 0.075, 0.050], ashD: 0.0034, ashFall: 0.30,
    vaultC: [0.038, 0.038, 0.048], vaultI: 0.34,
    paleC: [0.50, 0.44, 0.40], paleI: 0.05, paleEl: 0.55, paleAz: 2.30,
    lavaC: [1.00, 0.48, 0.16], crackI: 1.90, crackW: 0.195, fireI: 4.4, glowH: 30,
    crustC: [1.00, 0.92, 0.88], sulphC: [0.70, 0.60, 0.22],
    warp: 1.40, steamI: 1.45, sparkI: 2.00, scorch: 0.72, starI: 0.0,
    gustX: 0.22, gustZ: 0.10, birdRate: 1.5, bloom: 0.52, exposure: 0.93 },
  'ashfall': {
    caption: 'Ash comes down heavy enough to bury the seams. The glow no longer reaches anything — it just sits in the air, a few metres deep.',
    ashC: [0.078, 0.068, 0.062], ashD: 0.0105, ashFall: 1.00,
    vaultC: [0.050, 0.047, 0.046], vaultI: 0.34,
    paleC: [0.48, 0.42, 0.38], paleI: 0.05, paleEl: 0.80, paleAz: 2.30,
    lavaC: [1.00, 0.36, 0.11], crackI: 0.68, crackW: 0.115, fireI: 1.8, glowH: 12,
    crustC: [0.84, 0.81, 0.79], sulphC: [0.58, 0.54, 0.26],
    warp: 0.35, steamI: 0.60, sparkI: 0.25, scorch: 0.95, starI: 0.0,
    gustX: 0.75, gustZ: 0.35, birdRate: 0.4, bloom: 0.26, exposure: 1.08 },
  'night-glow': {
    caption: 'No daylight at all. The floor is the only lamp left, the crust reads as the negative of its own cracks, and a few stars survive the zenith.',
    ashC: [0.048, 0.036, 0.034], ashD: 0.0036, ashFall: 0.12,
    vaultC: [0.022, 0.026, 0.044], vaultI: 0.55,
    paleC: [0.30, 0.36, 0.55], paleI: 0.015, paleEl: 1.10, paleAz: 2.30,
    lavaC: [1.00, 0.31, 0.08], crackI: 1.15, crackW: 0.300, fireI: 2.7, glowH: 24,
    crustC: [1.00, 0.94, 0.90], sulphC: [0.60, 0.53, 0.22],
    warp: 0.80, steamI: 1.10, sparkI: 1.40, scorch: 0.60, starI: 1.0,
    gustX: 0.08, gustZ: 0.04, birdRate: 0.6, bloom: 0.62, exposure: 1.05 },
};
const ORDER = Object.keys(STATES);
const isColor = (k) => Array.isArray(STATES[ORDER[0]][k]);

const sceneDef = {
  meta: { fov: 62, near: 0.1, far: 1600, pixelRatio: 1.5, rate: 1.1, seed: 11, toneMapping: 'ACESFilmicToneMapping' },

  buildUniforms() {
    return {
      uTime: F(0),
      uAshC: C3(), uAshD: F(0.006), uAshFall: F(0.3),
      uVaultC: C3(), uVaultI: F(0.5),
      uPaleDir: V3(0, -1, 0), uPaleC: C3(), uPaleI: F(0.2),
      uLavaC: C3(), uCrustC: C3(), uSulphC: C3(),
      uCrackI: F(1), uCrackW: F(0.16), uFireI: F(5), uGlowH: F(20), uWarp: F(0.6),
      uSteamI: F(1), uSparkI: F(1), uScorch: F(0.6), uStarI: F(0),
      uBowlR: F(BOWL), uRimY: F(RIM),
      uGust: { value: new THREE.Vector2(0.12, 0.05) },
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
    U.uAshC.value.copy(cur.ashC); U.uAshD.value = cur.ashD; U.uAshFall.value = cur.ashFall;
    U.uVaultC.value.copy(cur.vaultC); U.uVaultI.value = cur.vaultI;
    U.uPaleC.value.copy(cur.paleC); U.uPaleI.value = cur.paleI;
    U.uLavaC.value.copy(cur.lavaC); U.uCrustC.value.copy(cur.crustC); U.uSulphC.value.copy(cur.sulphC);
    U.uCrackI.value = cur.crackI; U.uCrackW.value = cur.crackW;
    U.uFireI.value = cur.fireI; U.uGlowH.value = cur.glowH; U.uWarp.value = cur.warp;
    U.uSteamI.value = cur.steamI; U.uSparkI.value = cur.sparkI;
    U.uScorch.value = cur.scorch; U.uStarI.value = cur.starI;
    U.uGust.value.set(cur.gustX, cur.gustZ);
    // the weak overhead term. There is no sun here: this is diffuse daylight or
    // starlight arriving through ash, and it never outweighs what fireLight() adds.
    const ce = Math.cos(cur.paleEl);
    U.uPaleDir.value.set(-ce * Math.sin(cur.paleAz), -Math.sin(cur.paleEl), -ce * Math.cos(cur.paleAz)).normalize();
  },

  setup(ctx) { ctx.scene.background = ctx.U.uAshC.value; },

  layers: [Crust, Vault, Scorch, Skein, Plumes],
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
