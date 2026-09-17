import * as THREE from 'three';
import { uniformsFor, F, C3 } from '../contract/runtime.js';
import { VERT_WORLD, FRAG_ICE } from './prelude.glsl.js';

// Material factories built by string-surgery on the shared bases. Reach for these
// before writing a raw ShaderMaterial: they carry this world's crevasse shading,
// subsurface glow, snow upwash and thin-air aerial perspective, so a mesh sits ON
// the glacier rather than in front of a picture of one.

export const iceMat = (ctx, opts = {}) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, {
    uGrit: F(opts.grit ?? 1),
    uBare: F(opts.bare ?? 0.25),
    uRocky: F(opts.rocky ?? 1),
    uFlex: F(0),
  }),
  vertexShader: VERT_WORLD, fragmentShader: FRAG_ICE, side: opts.side ?? THREE.FrontSide,
});

// string surgery that fails loudly: a .replace() whose anchor has drifted out of the
// prelude silently returns the original shader, and the layer then renders as the
// thing it was derived from instead of the thing it was meant to be.
const cut = (src, from, to) => { if (src.indexOf(from) < 0) throw new Error(`materials.js: anchor not found: ${from.slice(0, 48)}`); return src.split(from).join(to); };

// Lichen and moss cushions: ice shading swapped for a crust palette, plus a carved
// silhouette. A quad is a rectangle; a moss cushion clinging to a moraine block is
// not — without the alpha discard the moraine grows rows of coloured postage stamps.
export const VERT_CRUST = cut(cut(VERT_WORLD,
  'varying vec3 vP, vN;', 'varying vec3 vP, vN, vTint; varying vec2 vUv; attribute vec3 aTint;'),
  'vP = wp.xyz;', 'vP = wp.xyz; vTint = aTint; vUv = uv;');

export const FRAG_CRUST = cut(cut(cut(FRAG_ICE,
  'varying vec3 vP, vN; uniform float uGrit, uBare, uRocky;',
  'varying vec3 vP, vN, vTint; varying vec2 vUv; uniform float uGrit, uBare, uRocky;'),
  'void main(){ vec3 p = vP;', `void main(){ vec3 p = vP;
  /* per-cushion offset so neighbouring instances are not the same silhouette */
  vec2 co = floor(p.xz * 4.0);
  float rad = abs(vUv.x - 0.5) * 2.0;
  float y = clamp(vUv.y, 0.0, 1.0);
  /* a squat dome broken into lobes, then eaten away at the edges */
  float lobes = 0.72 + 0.34 * turb2(vec2(y * 4.0, 0.0) + co) + 0.16 * sin(y * 9.0 + turb2(co) * 6.28);
  float prof = sqrt(max(1.0 - y * y * 0.94, 0.0)) * lobes;
  float erode = 0.55 + 0.80 * turb2(vec2(vUv.x * 15.0, y * 19.0) + co * 2.7);
  if (rad > prof * erode) discard;
  if (turb2(vec2(vUv.x * 30.0, y * 26.0) + co * 6.1) < 0.33) discard;   /* open it into stems and grit */`),
  'vec3 base = mix(mix(snow, blue, bare), rock, rockF) * (1.0 - 0.42 * cv);',
  `vec3 base = mix(vTint, vec3(0.50, 0.47, 0.34), uLichenD * 0.55) * (0.70 + 0.55 * vnz3(p * 16.0));
  rockF = 1.0; cv = 0.0;                                               /* crust is opaque: no ice glow */`);

export const crustMat = (ctx) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uGrit: F(0.4), uBare: F(0.0), uRocky: F(1), uFlex: F(0.35) }),
  vertexShader: VERT_CRUST, fragmentShader: FRAG_CRUST, side: THREE.DoubleSide,
});
