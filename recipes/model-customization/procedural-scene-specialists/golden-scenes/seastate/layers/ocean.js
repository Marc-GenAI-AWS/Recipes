import * as THREE from 'three';
import { atmosphereUniformsGLSL, atmosphereGLSL } from '../prelude.glsl.js';
import { uniformsFor } from '../../contract/runtime.js';

// Grid warped so vertex density concentrates near the camera: fine detail up
// close, long cheap triangles out at the horizon.
function makeOceanGeometry(N, half, expo) {
  const verts = (N + 1) * (N + 1);
  const positions = new Float32Array(verts * 3);
  let ptr = 0;
  for (let iz = 0; iz <= N; iz++) {
    const uz = (iz / N) * 2 - 1;
    const z = Math.sign(uz) * Math.pow(Math.abs(uz), expo) * half;
    for (let ix = 0; ix <= N; ix++) {
      const ux = (ix / N) * 2 - 1;
      const x = Math.sign(ux) * Math.pow(Math.abs(ux), expo) * half;
      positions[ptr++] = x;
      positions[ptr++] = 0;
      positions[ptr++] = z;
    }
  }
  const index = new Uint32Array(N * N * 6);
  ptr = 0;
  for (let iz = 0; iz < N; iz++) {
    for (let ix = 0; ix < N; ix++) {
      const a = iz * (N + 1) + ix;
      const b = a + 1;
      const c = a + (N + 1);
      const d = c + 1;
      index[ptr++] = a; index[ptr++] = c; index[ptr++] = b;
      index[ptr++] = b; index[ptr++] = c; index[ptr++] = d;
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setIndex(new THREE.BufferAttribute(index, 1));
  return geo;
}

/* ═══ COMPONENT: Ocean (ground/water) ═══
   Gerstner-wave water surface. Reads the shared palette + sea knobs from cur;
   owns its wave-time clock and its water material uniforms. */
export class Ocean {
  constructor(ctx) {
    this.ctx = ctx;
    this.waveTime = 0;
    const geo = makeOceanGeometry(320, 2600, 1.7);

    const mat = new THREE.ShaderMaterial({
      defines: { CLOUD_OCT: 3 },
      uniforms: uniformsFor(ctx.U, {
        uWaveTime: { value: 0 },
        uAmpMul: { value: 0.4 },
        uChopMul: { value: 0.8 },
        uWaterDeep: { value: new THREE.Color(0.015, 0.08, 0.14) },
        uWaterShallow: { value: new THREE.Color(0.05, 0.28, 0.3) },
        uFoamAmount: { value: 0.2 },
        uDetail: { value: 0.25 },
        uSpecPower: { value: 700 },
        uSpec: { value: 1.0 },
        uFogDensity: { value: 0.0013 },
      }),
      vertexShader: /* glsl */ `
        uniform float uWaveTime;
        uniform float uAmpMul;
        uniform float uChopMul;

        varying vec3 vWorldPos;
        varying vec3 vNormal;
        varying float vFoam;
        varying float vHeight;

        vec3 waveAdd(vec2 p, vec2 dir, float L, float amp, float t) {
          float k = 6.2831853 / L;
          float c = sqrt(9.81 / k);
          vec2 D = normalize(dir);
          float f = k * (dot(D, p) - c * t);
          float A = amp * uAmpMul;
          float s = sin(f);
          float co = cos(f);
          return vec3(D.x * uChopMul * A * co, A * s, D.y * uChopMul * A * co);
        }

        vec3 displace(vec2 p, float t) {
          vec3 d = vec3(0.0);
          d += waveAdd(p, vec2(1.0,  0.12), 101.0, 0.55,  t);
          d += waveAdd(p, vec2(1.0, -0.06),  63.0, 0.80,  t);
          d += waveAdd(p, vec2(0.94, -0.34), 31.0, 0.42,  t);
          d += waveAdd(p, vec2(0.83,  0.55), 17.0, 0.25,  t);
          d += waveAdd(p, vec2(0.70, -0.72),  8.9, 0.14,  t);
          d += waveAdd(p, vec2(0.96,  0.28),  4.7, 0.065, t);
          return d;
        }

        void main() {
          vec2 p = position.xz;
          float t = uWaveTime;

          vec3 dp = displace(p, t);
          vec3 wp = vec3(p.x, 0.0, p.y) + dp;

          float e = 1.2;
          vec3 px = vec3(p.x + e, 0.0, p.y) + displace(p + vec2(e, 0.0), t);
          vec3 pz = vec3(p.x, 0.0, p.y + e) + displace(p + vec2(0.0, e), t);
          vec3 tx = px - wp;
          vec3 tz = pz - wp;
          vNormal = normalize(cross(tz, tx));

          // horizontal squeeze at crests -> whitecaps
          float J = (tx.x * tz.z - tx.z * tz.x) / (e * e);
          float crest = clamp(1.0 - J, 0.0, 1.0);
          vFoam = crest * 1.4 + max(dp.y, 0.0) * 0.12;

          vHeight = dp.y;
          vWorldPos = wp;
          gl_Position = projectionMatrix * viewMatrix * vec4(wp, 1.0);
        }
      `,
      fragmentShader:
        atmosphereUniformsGLSL +
        /* glsl */ `
        uniform vec3  uWaterDeep;
        uniform vec3  uWaterShallow;
        uniform float uFoamAmount;
        uniform float uDetail;
        uniform float uSpecPower;
        uniform float uSpec;
        uniform float uFogDensity;

        varying vec3 vWorldPos;
        varying vec3 vNormal;
        varying float vFoam;
        varying float vHeight;
        ` +
        atmosphereGLSL +
        /* glsl */ `
        void main() {
          vec3 V = vWorldPos - cameraPosition;
          float dist = length(V);
          V /= dist;

          vec3 n = normalize(vNormal);

          // procedural detail ripples, faded with distance to avoid shimmer.
          // second octave is rotated ~60 deg and counter-scrolled so the two
          // layers never align into corduroy stripes
          float detFade = uDetail / (1.0 + dist * 0.06);
          mat2 rot = mat2(0.5, -0.866, 0.866, 0.5);
          vec2 dp = vWorldPos.xz * 0.6 + vec2(uTime * 0.45, uTime * 0.2);
          float e = 0.35;
          #define RIPPLE(P) (vnoise(P) + 0.5 * vnoise(rot * (P) * 2.7 - vec2(uTime * 0.31, uTime * 0.12)))
          float h0 = RIPPLE(dp);
          float hx = RIPPLE(dp + vec2(e, 0.0));
          float hz = RIPPLE(dp + vec2(0.0, e));
          n = normalize(n + vec3(h0 - hx, 0.0, h0 - hz) * (detFade / e));

          float NdV = max(dot(n, -V), 0.0);
          float fres = 0.02 + 0.98 * pow(1.0 - NdV, 5.0);

          vec3 R = reflect(V, n);
          R.y = max(R.y, 0.02);
          vec3 refl = skyRadiance(normalize(R));

          // water body: deep color in troughs, scatter color at crests,
          // plus light punching through crests when looking toward a low sun
          float sunUp = clamp(uSunDir.y * 4.0, 0.0, 1.0);
          vec3 body = mix(uWaterDeep, uWaterShallow, clamp(vHeight * 0.25 + 0.2, 0.0, 1.0));
          float sss = pow(max(dot(V, -uSunDir) * 0.5 + 0.5, 0.0), 3.0);
          sss *= clamp(vHeight * 0.6 + 0.3, 0.0, 1.5) * sunUp;
          body += uWaterShallow * sss * 0.8;

          vec3 col = mix(body, refl, fres);

          // sun glitter: tight sparkle plus a broad sheen
          vec3 H = normalize(-V + uSunDir);
          float ndh = max(dot(n, H), 0.0);
          float specMask = clamp(uSunDir.y * 8.0, 0.0, 1.0);
          col += uSunTint * (pow(ndh, uSpecPower) * 1.2 + pow(ndh, uSpecPower * 0.08) * 0.08) * uSpec * specMask;

          // moon glitter path
          vec3 Hm = normalize(-V + uMoonDir);
          float ndhm = max(dot(n, Hm), 0.0);
          col += vec3(0.8, 0.9, 1.0) * (pow(ndhm, 900.0) * 2.2 + pow(ndhm, 90.0) * 0.03) * uMoon;

          // foam, broken up by noise
          float fn = vnoise(vWorldPos.xz * 0.9 + uTime * 0.25) * 0.6
                   + vnoise(vWorldPos.xz * 3.1 - uTime * 0.2) * 0.4;
          float foam = clamp(vFoam * uFoamAmount, 0.0, 1.5);
          float fmask = smoothstep(0.45, 0.75, foam * (0.55 + 0.45 * fn));
          vec3 foamCol = uHorizon * 1.1 + uSunTint * 0.4 + vec3(0.05);
          col = mix(col, foamCol, fmask * clamp(uFoamAmount, 0.0, 1.0));

          // lightning ambience on the water
          col += vec3(0.55, 0.62, 0.8) * uLightning * 0.25;

          // fade into the sky at the horizon (fog samples the actual sky)
          vec3 hd = normalize(vec3(V.x, 0.0, V.z));
          vec3 horizonCol = skyRadiance(hd);
          float fogF = 1.0 - exp(-dist * uFogDensity);
          col = mix(col, horizonCol, fogF);

          col = acesTonemap(col * uExposure);
          col = pow(col, vec3(0.4545));
          col += (hash21(gl_FragCoord.xy) - 0.5) / 255.0;
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.frustumCulled = false;
    ctx.scene.add(mesh);
    this.mat = mat;
  }
  update(dt) {
    const cur = this.ctx.cur, u = this.mat.uniforms;
    this.waveTime += dt * cur.speedMul;
    u.uWaveTime.value = this.waveTime;
    u.uAmpMul.value = cur.ampMul;
    u.uChopMul.value = cur.chopMul;
    u.uWaterDeep.value.copy(cur.waterDeep);
    u.uWaterShallow.value.copy(cur.waterShallow);
    u.uFoamAmount.value = cur.foamAmount;
    u.uDetail.value = cur.detail;
    u.uSpecPower.value = cur.specPower;
    u.uSpec.value = cur.spec;
    u.uFogDensity.value = cur.fogDensity;
  }
}
