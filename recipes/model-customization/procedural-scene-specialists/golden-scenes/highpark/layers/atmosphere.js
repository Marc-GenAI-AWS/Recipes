import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Atmosphere ═══
   Sky dome: gradient, sun disc through the gap, cumulus field / storm shelf,
   the break above the saddle, dusk stars, lightning kiss on the cloud bases. */
export class Atmosphere {
  constructor(ctx) {
    const { scene, U } = ctx;
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(1200, 48, 24), new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, uniforms: uniformsFor(U, {}),
      vertexShader: `varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      uniform float uStars; varying vec3 vD;
      void main(){ vec3 d = normalize(vD); float h = max(d.y, 0.0);
        /* base gradient: pull the visible near-horizon band well toward the blue zenith so it
           reads as a real sky and white clouds have something to contrast against */
        vec3 col = mix(uSkyHorizon, uSkyTop, 0.18 + 0.72 * smoothstep(0.0, 0.6, h));
        float s = max(dot(d, normalize(uSunDir)), 0.0);
        col += uSunC * (pow(s, 900.0) * 4.0 + pow(s, 16.0) * 0.4 + pow(s, 3.0) * 0.08) * uSunI;   /* sun disc + glow */
        /* cumulus — near-horizontal views foreshorten the sky, so sample at HIGH horizontal
           frequency (|d.y|+small k, never /d.y) to get separate puffs across the frame */
        vec2 cuv = d.xz / (abs(d.y) + 0.18);
        vec2 drift = vec2(uTime * 0.02 * (0.4 + uWind), uTime * 0.008);
        float cov = fbm2(cuv * 2.2 + drift);              /* fbm here is ~0..0.94; DON'T *0.5+0.5 or coverage saturates */
        float det = fbm2(cuv * 5.5 + drift * 1.7);
        float puff = cov * 0.62 + det * 0.38;
        float band = smoothstep(0.02, 0.14, h) * smoothstep(1.0, 0.45, h);             /* clouds ride a band above the peaks */
        float cloud = smoothstep(0.5 - uCloud * 0.24, 0.60, puff) * band;             /* partial coverage → distinct puffs */
        /* shade: shadowed grey-blue underside vs bright sunlit top, so cumulus have real form */
        float litc = smoothstep(0.3, 0.62, det);
        vec3 cbase = mix(vec3(0.40, 0.44, 0.52), uFogC * 0.55, 0.35);                   /* cool shadowed base */
        vec3 ctop = mix(vec3(1.25), uSunC, 0.18 * uSunI);                               /* bright sunlit top */
        vec3 cloudCol = mix(cbase, ctop, litc) * (0.72 + 0.35 * uSunI) + uSunC * pow(s, 2.0) * 0.4 * uSunI;
        /* storm shelf: a heavy overcast that darkens the whole sky band, not just the puffs */
        vec3 stormCol = mix(uSkyTop, uFogC, 0.55) * 0.72;
        float over = smoothstep(0.55, 0.95, uCloud) * band;
        col = mix(col, stormCol, over * 0.6);
        cloudCol = mix(cloudCol, stormCol * 0.85, smoothstep(0.55, 0.95, uCloud));
        col = mix(col, cloudCol, cloud);
        /* the break above the saddle: clouds thin and a little sun leaks through */
        float gap = exp(-pow(length(d.xz - normalize(uSaddle).xz) * 2.6, 2.0));
        col = mix(col, mix(col, uSunC * (0.6 + uSunI), 0.5), gap * uShaft * 0.4 * (1.0 - h * 0.6));
        vec2 sp = d.xz / max(d.y, 0.05) * 70.0; vec2 cell = floor(sp);
        float stv = step(0.95, hash1(vec3(cell, 1.0)));
        float star = smoothstep(0.09, 0.0, length(fract(sp) - 0.5 - 0.3 * (vec2(hash1(vec3(cell, 2.0)), hash1(vec3(cell, 3.0))) - 0.5))) * stv;
        col += star * uStars * smoothstep(0.12, 0.5, h) * (1.0 - cloud);
        col += uFlash * FLASH_C * (0.15 + 0.5 * cloud) * (1.0 - h * 0.4);               /* lightning kisses the cloud bases (kept low so the bolt stays visible) */
        col = mix(col, uFogC, smoothstep(0.05, 0.0, h) * 0.55);                         /* soft haze right at the horizon line */
        gl_FragColor = vec4(col, 1.0);` + TAIL })));
  }
}
