import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Aether (the sky) ═══
   Air at 3500 m is thin enough to be almost black overhead and blinding within ten
   degrees of the sun. That gradient is the widest contrast in the scene and the
   reason the snow reads as bright rather than merely pale — so the dome carries the
   sun disc, its aureole, the 22° halo and the two sundogs that ice crystals in the
   air throw either side of it. */
export class Aether {
  constructor(ctx) {
    this.ctx = ctx;
    const geo = new THREE.SphereGeometry(900, 48, 32);
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: uniformsFor(ctx.U, {}),
      vertexShader: `varying vec3 vDir;
        void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vDir;
      void main(){
        vec3 d = normalize(vDir);
        vec3 s = -uSolarV;
        float up = clamp(d.y * 0.5 + 0.5, 0.0, 1.0);
        /* deep at the zenith, bleached white at the horizon where the air piles up */
        vec3 col = mix(uAirC, uZenithC, pow(clamp(d.y, 0.0, 1.0), 0.36)) * (0.85 + 0.35 * uDomeI);

        float sd = clamp(dot(d, s), -1.0, 1.0);
        float ang = acos(sd);
        /* the sun: a small hard disc inside an enormous aureole. uGlareI is what
           makes this world painful to look at rather than merely light. */
        col += uSolarC * uSolarI * uGlareI *
               (smoothstep(0.011, 0.004, ang) * 7.0 + pow(max(sd, 0.0), 260.0) * 2.2
              + pow(max(sd, 0.0), 14.0) * 0.55 + pow(max(sd, 0.0), 3.0) * 0.14);

        /* 22° halo and the two parhelia, thrown by plate crystals drifting in the air */
        float halo = smoothstep(0.012, 0.0, abs(ang - 0.384)) * (1.0 + 0.6 * smoothstep(0.40, 0.384, ang));
        col += mix(vec3(1.0, 0.92, 0.80), vec3(0.85, 0.95, 1.0), smoothstep(0.384, 0.40, ang)) * halo * uHaloI * 0.9;
        vec3 sx = normalize(cross(vec3(0.0, 1.0, 0.0), s));
        for (int k = 0; k < 2; k++) {
          vec3 dogv = normalize(s + sx * (k == 0 ? 0.404 : -0.404));
          float dg = max(dot(d, dogv), 0.0);
          col += vec3(1.0, 0.90, 0.74) * uHaloI * pow(dg, 900.0) * 3.4;
        }

        /* alpenglow: the low sun reddens the band of air the peaks stand in */
        col += vec3(1.0, 0.42, 0.34) * uAlpenI * pow(max(0.5 + 0.5 * sd, 0.0), 3.0)
             * smoothstep(0.34, -0.02, d.y) * smoothstep(-0.16, 0.02, d.y);

        /* cloud dropping into the basin: the dome loses its gradient entirely */
        float cl = 0.45 + 0.55 * turb3(d * 6.0 + vec3(uTime * 0.02, 0.0, 0.0));
        col = mix(col, uAirC * (0.92 + 0.30 * cl), uWhiteout * smoothstep(-0.25, 0.55, d.y) * 0.96);
        col = mix(col, uAirC, pow(1.0 - up, 3.0) * 0.55 * (1.0 - uWhiteout));
        gl_FragColor = vec4(col, 1.0);
      ` + TAIL,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);
  }
  update() { const { camera } = this.ctx; this.mesh.position.copy(camera.position); }
}
