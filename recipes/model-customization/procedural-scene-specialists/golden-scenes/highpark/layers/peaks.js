import * as THREE from 'three';
import { uniformsFor, C3, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { groundH, ridged, SADDLE } from '../field.js';

/* ═══ COMPONENT: Peaks ═══
   Ridged heightfield ring behind the basin with snow-by-altitude (per-vertex,
   not per-triangle, so nothing speckles) and two silhouette ranks in the haze.
   Owns its snow/rock colour uniforms (published from cur each frame). */
export class Peaks {
  constructor(ctx) {
    const { scene, U } = ctx;
    this.ctx = ctx;
    /* near range: a smooth ridged heightfield across the north of the basin.
       Summits are raised well clear of the haze; snow is computed per-vertex
       from world altitude (smooth, not per-triangle) so nothing speckles. */
    const W = 1100, D = 420, SEG_X = 480, SEG_Z = 130;
    const geo = new THREE.PlaneGeometry(W, D, SEG_X, SEG_Z); geo.rotateX(-Math.PI / 2); geo.translate(0, 0, -480);
    const pos = geo.attributes.position, aSnow = new Float32Array(pos.count);
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), z = pos.getZ(i);
      const depth = THREE.MathUtils.clamp((-z - 250) / 240, 0, 1);                     /* 0 basin edge → 1 back */
      const gap = 1 - 0.72 * Math.exp(-((x - SADDLE.x) ** 2) / (2 * 46 * 46));          /* the saddle notch */
      const relief = Math.pow(ridged(x * 0.0030, 2.1) * gap, 1.3) + ridged(x * 0.0072, 5.7) * 0.28;
      const y = groundH(x, z) + depth * depth * (26 + relief * 300);
      pos.setY(i, y);
      aSnow[i] = THREE.MathUtils.smoothstep(y, 88, 175);                                /* clean snow line by height */
    }
    geo.setAttribute('aSnow', new THREE.BufferAttribute(aSnow, 1));
    geo.computeVertexNormals();
    const mat = new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, { uSnow: C3(), uRock: C3() }),
      vertexShader: `varying vec3 vP, vN; varying float vSnow; attribute float aSnow;
      void main(){ vec4 wp = modelMatrix * vec4(position, 1.0); vP = wp.xyz; vN = normalize(mat3(modelMatrix) * normal); vSnow = aSnow;
        gl_Position = projectionMatrix * viewMatrix * wp; }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP, vN; varying float vSnow; uniform vec3 uSnow, uRock;
      void main(){ vec3 p = vP, n = normalize(vN);
        float slope = 1.0 - n.y;
        float snow = vSnow * smoothstep(0.72, 0.42, slope);                             /* snow slides off cliffs, softly */
        float strata = 0.5 + 0.5 * sin(p.y * 0.13 + fbm2(p.xz * 0.02) * 2.5);
        vec3 rock = uRock * (0.82 + 0.24 * strata);
        vec3 turf = mix(uRock, vec3(0.20, 0.26, 0.13), 0.7);                            /* grassy apron low down */
        vec3 base = mix(mix(turf, rock, smoothstep(20.0, 55.0, p.y)), uSnow, snow);
        float lam = max(dot(n, normalize(uSunDir)), 0.0);
        vec3 sky = mix(uSkyHorizon, uSkyTop, 0.5);
        vec3 light = sky * (0.42 + 0.26 * max(n.y, 0.0)) + uSunC * uSunI * lam * (0.55 + 0.45 * cloudShad(p));
        light += uSunC * uSunI * pow(lam, 2.5) * snow * 0.7;                            /* alpenglow / snow glare */
        gl_FragColor = vec4(fog(base * light, p), 1.0);` + TAIL });
    this.mat = mat; scene.add(new THREE.Mesh(geo, mat));
    /* two soft silhouette ranks fading into the haze behind */
    for (const [zz, hh, sd, mixA] of [[-820, 210, 3.3, 0.55], [-1080, 260, 8.9, 0.78]]) {
      const g2 = new THREE.PlaneGeometry(3200, 620, 260, 1);
      const p2 = g2.attributes.position;
      for (let i = 0; i < p2.count; i++) { if (p2.getY(i) > 0) p2.setY(i, ridged(p2.getX(i) * 0.0026, sd) * hh - hh * 0.15); else p2.setY(i, -240); }
      g2.computeVertexNormals();
      const m2 = new THREE.Mesh(g2, new THREE.ShaderMaterial({
        uniforms: uniformsFor(U, { uSnow: mat.uniforms.uSnow, uRock: mat.uniforms.uRock, uMixA: F(mixA) }),
        vertexShader: `varying vec3 vP; void main(){ vec4 wp = modelMatrix * vec4(position, 1.0); vP = wp.xyz; gl_Position = projectionMatrix * viewMatrix * wp; }`,
        fragmentShader: G + `
        varying vec3 vP; uniform vec3 uSnow, uRock; uniform float uMixA;
        void main(){ float snow = smoothstep(0.42, 0.66, clamp(vP.y / 200.0, 0.0, 1.0));
          vec3 col = mix(uRock, uSnow, snow) * (0.5 + 0.5 * uSunI);
          gl_FragColor = vec4(mix(col, uFogC, uMixA), 1.0);` + TAIL }));
      m2.position.z = zz; m2.renderOrder = -1; scene.add(m2);
    }
  }
  update() { const cur = this.ctx.cur; this.mat.uniforms.uSnow.value.copy(cur.peakSnow); this.mat.uniforms.uRock.value.copy(cur.peakRock); }
}
