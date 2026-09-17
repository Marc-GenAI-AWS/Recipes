import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Firmament (the sky) ═══
   From the floor of a slot canyon the sky is a bright ribbon overhead, not a dome
   you stand under. It is the brightest thing in frame by a wide margin at noon and
   the only light source at night, so it carries the sun disc, the moon and stars. */
export class Firmament {
  constructor(ctx) {
    this.ctx = ctx;
    const geo = new THREE.SphereGeometry(300, 48, 32);
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: uniformsFor(ctx.U, {}),
      vertexShader: `varying vec3 vDir;
        void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vDir;
      void main(){
        vec3 d = normalize(vDir);
        float up = clamp(d.y * 0.5 + 0.5, 0.0, 1.0);
        /* desert sky: deep overhead, bleached and dusty toward the horizon */
        vec3 col = mix(uHazeC, uSkyC, pow(up, 0.65)) * uSkyI;

        /* sun disc and its aureole */
        float sd = max(dot(d, -uSunDir), 0.0);
        col += uSunC * uSunI * (pow(sd, 900.0) * 6.0 + pow(sd, 22.0) * 0.30 + pow(sd, 5.0) * 0.06);

        /* moon and stars, only where the night states raise them */
        if (uStars > 0.001) {
          vec3 sp = d * 90.0;
          float tw = noise3(floor(sp) + 0.5);
          float star = step(0.9965, hash1(floor(sp))) * (0.55 + 0.45 * sin(uTime * 2.0 + tw * 31.4));
          col += vec3(0.85, 0.9, 1.0) * star * uStars * smoothstep(0.05, 0.5, d.y);
        }
        if (uMoon > 0.001) {
          float md = max(dot(d, normalize(vec3(0.35, 0.72, -0.6))), 0.0);
          col += vec3(0.8, 0.86, 1.0) * uMoon * (pow(md, 2200.0) * 5.0 + pow(md, 26.0) * 0.12);
        }

        /* airborne dust washes the whole ribbon out */
        col = mix(col, uHazeC * (0.7 + 0.5 * uSkyI), uDust * 0.55);
        gl_FragColor = vec4(col, 1.0);
      ` + TAIL,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);
  }
  update() { const { camera } = this.ctx; this.mesh.position.copy(camera.position); }
}
