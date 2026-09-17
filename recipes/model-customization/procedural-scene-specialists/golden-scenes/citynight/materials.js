import * as THREE from 'three';
import { uniformsFor, F, C3 } from '../contract/runtime.js';
import { VERT_WORLD, FRAG_TARMAC, FRAG_BRICK } from './prelude.glsl.js';

// Material factories built by string-surgery on the shared bases. Reach for these
// before writing a raw ShaderMaterial: they already answer uEmi*/uWetness/uMurkD,
// so a mesh stands IN the street rather than beside it.

export const tarmacMat = (ctx, opts = {}) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uAggr: F(opts.aggr ?? 1), uSway: F(0) }),
  vertexShader: VERT_WORLD, fragmentShader: FRAG_TARMAC, side: opts.side ?? THREE.FrontSide,
});

// aFace rides the frontage instances: (seed, lit fraction, storey offset).
export const VERT_FACE = VERT_WORLD
  .replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vFace; attribute vec3 aFace;')
  .replace('vP = wp.xyz;', 'vP = wp.xyz; vFace = aFace;');

// uPane 0 turns the window grid off, which is what street furniture and car bodies
// want: the same soot-dark masonry shading with nothing lit in it.
export const brickMat = (ctx, brick, opts = {}) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, {
    uBrickC: { value: new THREE.Color(...brick) }, uPane: F(opts.pane ?? 1), uSway: F(0),
  }),
  vertexShader: VERT_FACE, fragmentShader: FRAG_BRICK, side: opts.side ?? THREE.FrontSide,
});

// Foliage: tarmac shading with the surface swapped for leaf matter, plus a
// silhouette carved out of the quad. aTuft = colour, aSprig = (seed, kind, ragged)
// where kind 0 is a weed in a crack and kind 1 a street-tree canopy cluster.
export const VERT_SPRIG = VERT_WORLD
  .replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vTuft, vSprig; varying vec2 vUv; attribute vec3 aTuft, aSprig;')
  .replace('vP = wp.xyz;', 'vP = wp.xyz; vTuft = aTuft; vSprig = aSprig; vUv = uv;');

// A quad is a rectangle; a plane tree is not. Carve the silhouette with an alpha
// discard — a lobed canopy for kind 1, a fan of blades for kind 0 — or the
// vegetation reads as coloured cardboard propped against the kerb.
export const FRAG_SPRIG = FRAG_TARMAC
  .replace('varying vec3 vP, vN; uniform float uAggr;',
           'varying vec3 vP, vN, vTuft, vSprig; varying vec2 vUv; uniform float uAggr;')
  .replace('void main(){ vec3 p = vP; vec3 g = normalize(vN);', `void main(){ vec3 p = vP; vec3 g = normalize(vN);
  float rad = abs(vUv.x - 0.5) * 2.0, yy = clamp(vUv.y, 0.0, 1.0);
  vec2 so = vec2(vSprig.x * 31.0, vSprig.x * 17.0);
  float prof, erode;
  if (vSprig.y > 0.5) {                                   /* canopy: a clump of lobes with sky through it */
    prof = (0.35 + 0.95 * sin(3.1416 * pow(yy, 0.8))) * (0.62 + 0.55 * fbm2(vec2(yy * 4.0, 0.0) + so));
    erode = 0.5 + 0.9 * fbm2(vec2(vUv.x * 9.0, yy * 11.0) + so * 2.3);
    if (rad > prof * erode) discard;
    if (fbm2(vec2(vUv.x * 21.0, yy * 25.0) + so * 5.1) < 0.34 + 0.22 * vSprig.z) discard;
  } else {                                                /* weed: straight blades splaying from a crack */
    float blade = abs(fract(vUv.x * 6.0 + 0.4 * fbm2(so)) - 0.5) * 2.0;
    prof = (1.0 - pow(yy, 1.1)) * (0.7 + 0.5 * fbm2(vec2(yy * 3.0, 0.0) + so));
    if (rad > prof) discard;
    if (blade > 0.42 - 0.3 * yy) discard;
  }`)
  .replace('vec3 base = uTarC * (0.62 + 0.55 * fbm3(p * 1.9) + 0.26 * noise3(p * 16.0));',
           'vec3 base = vTuft * (0.66 + 0.5 * noise3(p * 11.0)) * (0.55 + 0.75 * yy);')
  .replace('vec3 n = normalize(mix(nd, slickN(p, g), wet));', 'vec3 n = gl_FrontFacing ? nd : -nd;')
  .replace('float pool = puddleMask(p);', 'float pool = 0.0;')
  .replace('float wet = clamp(pool + 0.34 * uWetness, 0.0, 1.0);', 'float wet = 0.45 * uWetness;')
  .replace(/  if \(ax > uKerbX\) \{[\s\S]*?\n  \}\n/, '')
  .replace('base *= 1.0 - 0.30 * uGrime;', 'base *= 1.0 - 0.20 * uGrime;')
  .replace('vec3 lit = base * (skyBounce(n) + neonGlow(p, n)) + wetSpec(p, n) * mix(0.10, 1.0, wet);',
           'vec3 lit = base * (skyBounce(n) * 0.8 + neonGlow(p, n)) + wetSpec(p, n) * 0.25 * wet;')
  .replace('lit += uEmiC[0] * 0.02 * dropRings(p.xz * 1.15) * pool;', '');

export const sprigMat = (ctx) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uAggr: F(0.25), uSway: F(1) }),
  vertexShader: VERT_SPRIG, fragmentShader: FRAG_SPRIG, side: THREE.DoubleSide,
});
