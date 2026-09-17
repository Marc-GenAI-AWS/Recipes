import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { F } from '../contract/runtime.js';

/* ═══ COMPONENT: PostFX ═══
   Bloom + hand-written ACES pass (gamma + vignette); plain fallback if the
   composer is unavailable. Contract boilerplate (SCENE_CONTRACT §11). */
export class PostFX {
  constructor(ctx) {
    this.ctx = ctx;
    const { renderer, scene, camera } = ctx;
    try {
      this.composer = new EffectComposer(renderer); this.composer.addPass(new RenderPass(scene, camera));
      this.bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.4, 0.45, 0.92); this.composer.addPass(this.bloom);
      this.out = new ShaderPass({ uniforms: { tDiffuse: { value: null }, uExposure: F(1) }, vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
        fragmentShader: `uniform sampler2D tDiffuse; uniform float uExposure; varying vec2 vUv;
        vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
        void main(){ vec3 c = texture2D(tDiffuse, vUv).rgb * uExposure; c = aces(c); float v = 1.0 - 0.28 * pow(length(vUv - 0.5) * 1.35, 2.5);
          gl_FragColor = vec4(pow(c * v, vec3(1.0 / 2.2)), 1.0); }` });
      this.composer.addPass(this.out); renderer.toneMapping = THREE.NoToneMapping;
    } catch (e) { console.warn('post-processing unavailable, plain render', e); this.composer = null; }
  }
  resize(w, h) { if (this.composer) { this.composer.setSize(w, h); this.bloom.setSize(w, h); } }
  render() {
    const { renderer, scene, camera, cur } = this.ctx;
    if (this.composer) { this.bloom.strength = cur.bloom; this.out.uniforms.uExposure.value = cur.exposure; this.composer.render(); }
    else { renderer.toneMappingExposure = cur.exposure; renderer.render(scene, camera); }
  }
}
