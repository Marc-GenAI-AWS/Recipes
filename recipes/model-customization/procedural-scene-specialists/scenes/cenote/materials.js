import * as THREE from 'three';
import { uniformsFor, F, C3 } from '../contract/runtime.js';
import { VERT_WORLD, FRAG_ROCK } from './prelude.glsl.js';

// Material factories built by string-surgery on the shared bases (SCENE_CONTRACT §5).

export const rockMat = (ctx, base, opts = {}) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uBase: { value: new THREE.Color(...base) }, uMottle: F(opts.mottle ?? 1), uSway: F(opts.sway ?? 0) }),
  vertexShader: VERT_WORLD, fragmentShader: FRAG_ROCK, side: opts.side ?? THREE.FrontSide });

export const VERT_CORAL = VERT_WORLD
  .replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vCol; attribute vec3 aCol;')
  .replace('vP = wp.xyz;', 'vP = wp.xyz; vCol = aCol;');

export const FRAG_CORAL = FRAG_ROCK
  .replace('uniform vec3 uBase; uniform float uMottle;', 'uniform vec3 uBase; uniform float uMottle, uSat, uGlow; varying vec3 vCol;')
  .replace('vec3 base = uBase * ', 'vec3 base = mix(vec3(dot(vCol, vec3(0.33))), vCol, uSat * 0.85) * (0.78 + 0.36 * noise3(p * 16.0)) * (0.85 + 0.3 * noise3(p * 4.0 + 7.0)) * ')
  .replace('gl_FragColor = vec4(fog(base * light, p), 1.0);', 'gl_FragColor = vec4(fog(base * light + vCol * torchAt(p) * uGlow * 1.3 + base * uSunC * uSunI * 0.12 * bm, p), 1.0);');

export const coralMat = (ctx) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uBase: C3(), uMottle: F(0.35), uSway: F(0), uSat: ctx.U.uSat, uGlow: ctx.U.uGlow }),
  vertexShader: VERT_CORAL, fragmentShader: FRAG_CORAL });
