import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Overcast (the sky) ═══
   The night sky over a city is not black and it is not a star field: it is a low
   lid of cloud lit FROM BELOW by the streets under it. So the gradient runs the
   wrong way round — brightest at the rooftops, darkest straight up — and the
   cloud belly reads as texture in the sodium glow rather than silhouette.
   Stars only where the thinnest cloud lets one or two through, and only when the
   state raises uStarI at all. */
export class Overcast {
  constructor(ctx) {
    this.ctx = ctx;
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: uniformsFor(ctx.U, {}),
      vertexShader: `varying vec3 vDir;
        void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vDir;
      void main(){
        vec3 d = normalize(vDir);
        float up = clamp(d.y, 0.0, 1.0);
        /* lit from beneath: the lid burns where the city hits it and falls off upward */
        vec3 col = mix(uGlowC * 1.45, uGlowC * 0.16, pow(up, 0.55)) * uGlowI;

        /* cloud belly, dragged along the street by the gust; flattened toward the horizon */
        vec2 q = d.xz * (2.6 / max(up * 0.85 + 0.22, 0.2));
        float c = fbm3(vec3(q + uGust * uTime * 0.4, uTime * 0.012));
        col *= 0.66 + 0.85 * c;

        /* the sodium dome standing directly over the rooftops */
        col += uGlowC * uLampI * 0.55 * pow(1.0 - up, 7.0) * (0.6 + 0.6 * c);
        col = mix(col, uNeonC * uGlowI * 0.5, 0.18 * uHaloR * pow(1.0 - up, 4.0));

        /* almost no stars — only where the cloud is thinnest */
        if (uStarI > 0.001) {
          vec3 sp = d * 150.0;
          float tw = noise3(floor(sp) + 0.5);
          float star = step(0.9975, hash1(floor(sp))) * (0.5 + 0.5 * sin(uTime * 2.2 + tw * 31.4));
          col += vec3(0.80, 0.88, 1.0) * star * uStarI * smoothstep(0.25, 0.75, d.y) * smoothstep(0.62, 0.34, c);
        }

        /* rain and fog eat the lid from the horizon up */
        col = mix(col, uMurkC * (0.9 + 0.7 * uHaloR), clamp(0.35 * uRainAmt + 0.60 * uHaloR, 0.0, 0.95) * pow(1.0 - up, 1.7));
        gl_FragColor = vec4(col, 1.0);
      ` + TAIL,
    });
    this.mesh = new THREE.Mesh(new THREE.SphereGeometry(400, 40, 28), mat);
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);
  }
  update() { this.mesh.position.copy(this.ctx.camera.position); }
}
