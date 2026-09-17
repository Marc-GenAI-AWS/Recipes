import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Vault (the sky) ═══
   An ash pall over the caldera, and the darkest thing in frame in every state —
   which is the inversion this world exists for. It is not a light source; it is a
   lid. What brightness it has is BORROWED: the underside of the pall catches the
   orange coming up off the fissures, so the sky is brightest at the horizon and
   goes to soot at the zenith, exactly backwards from an open sky.

   Two features carry it. The ember band: an exponential lamp-from-below falloff in
   d.y, tinted by uLavaC and scaled by uCrackI, so opening the fissures visibly
   lights the cloud base. And the ash column: a single standing plume over the main
   vent, warm and churning at its foot, grey and shredded where it tops out. Stars
   only survive at the zenith, and only when uAshD lets them. */
export class Vault {
  constructor(ctx) {
    this.ctx = ctx;
    const geo = new THREE.SphereGeometry(700, 44, 30);
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: uniformsFor(ctx.U, {}),
      vertexShader: `varying vec3 vDir;
        void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vDir;
      void main(){
        vec3 d = normalize(vDir);
        float up = d.y;

        /* the pall itself: soot at the zenith, a shade warmer and denser low down */
        float lid = 0.45 + 0.55 * smoothstep(0.85, -0.25, up);
        vec2 q = d.xz / max(up + 0.42, 0.14);                   /* project onto the cloud base */
        float churn = turb2(q * 0.55 + vec2(uTime * 0.012, uTime * 0.008));
        vec3 col = uVaultC * uVaultI * lid * (0.55 + 0.95 * churn);

        /* THE INVERSION: the cloud base is lit from underneath by the floor */
        float lamp = exp(-max(up, -0.2) * 3.2);
        col += uLavaC * uCrackI * 0.045 * lamp * (0.35 + 1.15 * churn);

        /* the ash column standing over the main vent field */
        vec2 cd = normalize(vec2(0.52, -0.855));
        float aim = smoothstep(0.74, 0.995, dot(normalize(d.xz + vec2(1e-4)), cd));
        float shred = turb3(vec3(q * 1.6, uTime * 0.035));
        float plume = aim * smoothstep(-0.08, 0.30, up) * exp(-max(up, 0.0) * 1.15) * (0.25 + 1.3 * shred);
        col += mix(uLavaC * 0.42, uAshC, smoothstep(0.02, 0.42, up)) * plume * 0.16 * (0.28 + 0.9 * uCrackI);

        /* ash-filtered daylight, if the state has any: a diffuse smear, no disc */
        float pd = max(dot(d, -uPaleDir), 0.0);
        col += uPaleC * uPaleI * (0.05 + 0.50 * pow(pd, 6.0)) * smoothstep(-0.12, 0.6, up);

        /* almost no stars: only at the zenith, and only through thin ash */
        if (uStarI > 0.001) {
          vec3 sp = d * 110.0;
          float tw = vnz3(floor(sp) + 0.5);
          float st = step(0.9982, hashV(floor(sp))) * (0.5 + 0.5 * sin(uTime * 1.7 + tw * 28.0));
          col += vec3(0.72, 0.78, 0.95) * st * uStarI * smoothstep(0.42, 0.95, up) * exp(-uAshD * 140.0);
        }

        /* heavy ashfall closes the lid completely */
        col = mix(col, uAshC * (0.55 + 0.50 * churn) * (0.62 + 0.38 * lamp), uAshFall * 0.78);
        gl_FragColor = vec4(col, 1.0);
      ` + TAIL,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);
  }
  update() { this.mesh.position.copy(this.ctx.camera.position); }
}
