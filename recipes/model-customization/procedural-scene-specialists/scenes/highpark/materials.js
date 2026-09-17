import * as THREE from 'three';
import { uniformsFor, F } from '../contract/runtime.js';
import { VERT_WORLD, FRAG_MATTER } from './prelude.glsl.js';

// Base lit-matter material factory (rocks, horses). SCENE_CONTRACT §5.
export const matterMat = (ctx, base, opts = {}) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, { uBase: { value: new THREE.Color(...base) }, uMottle: F(opts.mottle ?? 1) }),
  vertexShader: VERT_WORLD, fragmentShader: FRAG_MATTER, side: opts.side ?? THREE.FrontSide });
