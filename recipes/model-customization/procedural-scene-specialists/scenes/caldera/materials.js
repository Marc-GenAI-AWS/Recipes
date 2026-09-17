import * as THREE from 'three';
import { uniformsFor, F, C3 } from '../contract/runtime.js';
import { VERT_WORLD, FRAG_CRUST } from './prelude.glsl.js';

// Material factories built by string-surgery on the shared bases. Reach for these
// before writing a raw ShaderMaterial: they carry fireLight(), the sulphur crusts
// and the ash veil, so a mesh stands IN the caldera — lit from below, dark on top —
// instead of beside it wearing ordinary daylight.

export const crustMat = (ctx, base, opts = {}) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, {
    uBaseC: { value: new THREE.Color(...base) },
    uRough: F(opts.rough ?? 1),
    uBend: F(opts.bend ?? 0),
  }),
  vertexShader: VERT_WORLD, fragmentShader: FRAG_CRUST, side: opts.side ?? THREE.FrontSide,
});

// Scorch: crust shading plus a per-instance tint and a scorch wash, so what little
// grows here answers the state's `scorch` the way the rock answers `crackI`.
export const VERT_SCORCH = VERT_WORLD
  .replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vTint; varying vec2 vUv; attribute vec3 aTint;')
  .replace('vP = wp.xyz;', 'vP = wp.xyz; vTint = aTint; vUv = uv;');

// A quad is a rectangle; a wind-burnt tussock is not. Carve the silhouette out of
// the quad with an alpha discard — splayed at the base, eaten away toward the tip —
// or the scrub reads as coloured cardboard propped on the ash, and worse here than
// anywhere, because every blade is backlit by the seams behind it.
export const FRAG_SCORCH = FRAG_CRUST
  .replace('varying vec3 vP, vN; uniform vec3 uBaseC; uniform float uRough;',
           'varying vec3 vP, vN, vTint; varying vec2 vUv; uniform vec3 uBaseC; uniform float uRough;')
  .replace('void main(){\n  vec3 p = vP;', `void main(){
  vec3 p = vP;
  /* per-clump offset so neighbouring instances are not the same silhouette */
  vec2 co = floor(p.xz * 2.7);
  float rad = abs(vUv.x - 0.5) * 2.0;
  float y = clamp(vUv.y, 0.0, 1.0);
  /* splayed tussock: wide and shaggy at the base, thinning to separated blades */
  float splay = (1.0 - pow(y, 0.72)) * (0.55 + 0.55*turb2(vec2(y*4.0, 0.0) + co))
              + 0.20*sin(y*13.0 + turb2(co)*6.28);
  float bite = 0.50 + 0.85*turb2(vec2(vUv.x*18.0, y*24.0) + co*3.7);
  if (rad > splay * bite) discard;
  if (turb2(vec2(vUv.x*30.0, y*38.0) + co*8.3) < 0.42 + 0.16*y) discard;   /* open it into blades */`)
  .replace('vec3 base = uBaseC * uCrustC * (1.0 - uRough*0.4 + uRough*0.95*m) * (0.80 + 0.30*m2);',
           `vec3 base = mix(vTint, vec3(0.30, 0.26, 0.22), uScorch*0.85)
              * (0.72 + 0.55*vnz3(p*12.0)) * (0.55 + 0.45*(1.0 - y));`)
  .replace('float glass = smoothstep(0.60, 0.92, turb3(p*0.16 + 3.0));', 'float glass = 0.0;')
  .replace('float su = sulphur(p);', 'float su = sulphur(p) * 0.4;');

export const scorchMat = (ctx) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uBaseC: C3(), uRough: F(0.35), uBend: F(1) }),
  vertexShader: VERT_SCORCH, fragmentShader: FRAG_SCORCH, side: THREE.DoubleSide,
});
