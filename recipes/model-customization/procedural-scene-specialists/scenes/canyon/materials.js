import * as THREE from 'three';
import { uniformsFor, F, C3 } from '../contract/runtime.js';
import { VERT_WORLD, FRAG_ROCK } from './prelude.glsl.js';

// Material factories built by string-surgery on the shared bases. Layers should
// reach for these before writing a raw ShaderMaterial: they carry this world's
// strata, bounce light and dust haze, so a mesh sits in the canyon rather than
// beside it.

export const rockMat = (ctx, rock, opts = {}) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, {
    uRockC: { value: new THREE.Color(...rock) },
    uGrain: F(opts.grain ?? 1),
    uSway: F(opts.sway ?? 0),
  }),
  vertexShader: VERT_WORLD, fragmentShader: FRAG_ROCK, side: opts.side ?? THREE.FrontSide,
});

// Scrub: rock shading plus per-instance colour and a dryness wash, so vegetation
// answers the state's `scrubDry` the way the rock answers `strata`.
export const VERT_SCRUB = VERT_WORLD
  .replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vCol; varying vec2 vUv; attribute vec3 aCol;')
  .replace('vP = wp.xyz;', 'vP = wp.xyz; vCol = aCol; vUv = uv;');

// A quad is a rectangle; a bush is not. Carve the silhouette out of the quad with
// an alpha discard — tapering toward the top and eroded by noise — or the scrub
// reads as coloured cardboard standing in the corridor.
export const FRAG_SCRUB = FRAG_ROCK
  .replace('uniform vec3 uRockC; uniform float uGrain;',
           'uniform vec3 uRockC; uniform float uGrain, uDry; varying vec3 vCol; varying vec2 vUv;')
  .replace('void main(){ vec3 p = vP;', `void main(){ vec3 p = vP;
  /* per-bush offset so neighbouring instances are not the same silhouette */
  vec2 bo = floor(p.xz * 3.0);
  float rad = abs(vUv.x - 0.5) * 2.0;
  float y = clamp(vUv.y, 0.0, 1.0);
  /* lumpy profile: a taper broken by a few lobes, so it is not a clean triangle */
  float lobes = 0.60 + 0.40 * fbm2(vec2(y * 3.5, 0.0) + bo)
              + 0.22 * sin(y * 11.0 + fbm2(bo) * 6.28);
  float prof = (1.0 - pow(y, 1.35)) * lobes;
  float erode = 0.55 + 0.75 * fbm2(vec2(vUv.x * 16.0, y * 22.0) + bo * 3.1);
  if (rad > prof * erode) discard;
  if (fbm2(vec2(vUv.x * 26.0, y * 34.0) + bo * 7.7) < 0.40) discard;   /* open it into twigs */`)
  .replace('vec3 base = uRockC * strata(p) * ',
           'vec3 base = mix(vCol, vec3(0.62, 0.53, 0.34), uDry * 0.8) * (0.8 + 0.35 * noise3(p * 14.0)) * ');

export const scrubMat = (ctx) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uRockC: C3(), uGrain: F(0.3), uSway: F(1), uDry: ctx.U.uDry }),
  vertexShader: VERT_SCRUB, fragmentShader: FRAG_SCRUB, side: THREE.DoubleSide,
});
