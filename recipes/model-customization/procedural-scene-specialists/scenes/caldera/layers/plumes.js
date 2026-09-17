import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { crustH, riftPhi, BOWL } from '../field.js';

/* ═══ COMPONENT: Plumes (the effects) ═══
   Three populations, all of them emitters or receivers of the floor's light.

   Steam — standing columns over the vents. Seeded on the CPU at points where
   riftPhi says there really is a seam, so no plume rises out of cold rock. Each
   puff is shaded by fireLight() with a DOWNWARD normal: it is a body of vapour
   with a lit underside, so the column is orange at its foot and goes grey-white
   as it climbs out of the glow. That gradient is the single clearest read of
   "lit from below" anywhere in the frame.

   Ashfall — fine grit coming down, wrapped in a box around the pan. Dark against
   the wall, and picked out warm when it falls past a seam.

   Embers — spark rising off the open cracks, additive and short-lived, keyed to
   emberAt() so they only exist where the fissure is actually open. They are the
   only thing in the world with genuinely random-looking motion, so they do most
   of the work of making the caldera feel alive rather than painted. */
export class Plumes {
  constructor(ctx) {
    this.ctx = ctx;
    this.steam = this.buildSteam(ctx);
    this.ash = this.buildAsh(ctx);
    this.embers = this.buildEmbers(ctx);
  }

  // find N points that really sit in a seam, using the shared CPU field
  seamPoints(ctx, n, tol) {
    const { rr } = ctx, out = [];
    let guard = 0;
    while (out.length < n && guard++ < n * 400) {
      const a = rr(0, Math.PI * 2), r = rr(14, BOWL - 14);
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      if (riftPhi(x, z) > tol) continue;
      out.push([x, crustH(x, z), z]);
    }
    while (out.length < n) out.push([0, crustH(0, 0), 0]);
    return out;
  }

  buildSteam(ctx) {
    const { rr } = ctx, N = 2600;
    const vents = this.seamPoints(ctx, 11, 0.14);
    const p = new Float32Array(N * 3), seed = new Float32Array(N), size = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const v = vents[i % vents.length];
      p[i * 3] = v[0] + rr(-1.8, 1.8); p[i * 3 + 1] = v[1] + rr(-0.3, 0.6); p[i * 3 + 2] = v[2] + rr(-1.8, 1.8);
      seed[i] = rr(0, 1); size[i] = rr(0.55, 1.25);
    }
    const g = pointGeo(p, seed, size);
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.NormalBlending,
      uniforms: uniformsFor(ctx.U, { uPlumeH: F(26) }),
      vertexShader: G + /* glsl */`
        attribute float aSeed, aSize; varying float vLife; varying vec3 vQ;
        uniform float uPlumeH;
        void main(){
          float sp = 0.055 + 0.055 * fract(aSeed * 7.13);
          float life = fract(uTime * sp + aSeed);
          vec3 q = position;
          float rise = life * uPlumeH;
          q.y += rise;
          float spread = 0.9 + 7.5 * life;
          q.x += spread * (turb2(vec2(aSeed * 91.0, life * 3.0)) - 0.5) * 2.0 + gustAt(q).x * rise * 0.09;
          q.z += spread * (turb2(vec2(aSeed * 37.0 + 5.0, life * 3.0)) - 0.5) * 2.0 + gustAt(q).y * rise * 0.09;
          vLife = life; vQ = q;
          vec4 mv = viewMatrix * vec4(q, 1.0);
          gl_PointSize = (3.0 + 15.0 * life) * aSize * (58.0 / max(-mv.z, 1.0));
          gl_Position = projectionMatrix * mv; }`,
      fragmentShader: G + /* glsl */`
        varying float vLife; varying vec3 vQ;
        void main(){
          float a = smoothstep(0.5, 0.06, length(gl_PointCoord - 0.5));
          a *= uSteamI * 0.21 * smoothstep(0.0, 0.10, vLife) * (1.0 - smoothstep(0.40, 0.95, vLife)) * exp(-max(vQ.y, 0.0) / 17.0);
          vec3 lit = uVaultC * uVaultI * 1.1 + uPaleC * uPaleI * 0.35
                   + fireLight(vQ, vec3(0.0, -1.0, 0.0)) * 0.42 * exp(-max(vQ.y, 0.0) / 9.0);
          vec3 col = mix(vec3(1.0, 0.96, 0.92), vec3(0.74, 0.74, 0.78), smoothstep(0.05, 0.6, vLife)) * lit;
          gl_FragColor = vec4(col, a * ashAtt(vQ));
        ` + TAIL,
    });
    return addPoints(ctx, g, mat);
  }

  buildAsh(ctx) {
    const { rr } = ctx, N = 3000;
    const p = new Float32Array(N * 3), seed = new Float32Array(N), size = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      p[i * 3] = rr(-110, 110); p[i * 3 + 1] = rr(0, 62); p[i * 3 + 2] = rr(-110, 110);
      seed[i] = rr(0, 100); size[i] = rr(0.5, 2.0);
    }
    const g = pointGeo(p, seed, size);
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.NormalBlending,
      uniforms: uniformsFor(ctx.U, {}),
      vertexShader: G + /* glsl */`
        attribute float aSeed, aSize; varying vec3 vQ; varying float vSz;
        void main(){
          vec3 q = position;
          vec2 w = gustAt(q);
          q.y -= mod(uTime * (1.2 + 1.8 * aSize) + aSeed * 13.0, 64.0);
          q.x += w.x * uTime * 2.2 + 1.4 * sin(uTime * 0.6 + aSeed);
          q.z += w.y * uTime * 2.2 + 1.4 * cos(uTime * 0.5 + aSeed * 1.7);
          q.x = mod(q.x + 110.0, 220.0) - 110.0;
          q.z = mod(q.z + 110.0, 220.0) - 110.0;
          q.y = mod(q.y + 2.0, 64.0) - 2.0;
          vQ = q; vSz = aSize;
          vec4 mv = viewMatrix * vec4(q, 1.0);
          gl_PointSize = aSize * (48.0 / max(-mv.z, 1.0));
          gl_Position = projectionMatrix * mv; }`,
      fragmentShader: G + /* glsl */`
        varying vec3 vQ; varying float vSz;
        void main(){
          float a = smoothstep(0.5, 0.12, length(gl_PointCoord - 0.5)) * uAshFall * 0.60;
          vec3 col = uAshC * (0.7 + 0.5 * vSz) * 0.9 + fireLight(vQ, vec3(0.0, -1.0, 0.0)) * 0.10;
          gl_FragColor = vec4(col, a * ashAtt(vQ));
        ` + TAIL,
    });
    return addPoints(ctx, g, mat);
  }

  buildEmbers(ctx) {
    const { rr } = ctx, N = 1500;
    const src = this.seamPoints(ctx, 220, 0.20);
    const p = new Float32Array(N * 3), seed = new Float32Array(N), size = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const v = src[i % src.length];
      p[i * 3] = v[0] + rr(-0.9, 0.9); p[i * 3 + 1] = v[1]; p[i * 3 + 2] = v[2] + rr(-0.9, 0.9);
      seed[i] = rr(0, 1); size[i] = rr(0.6, 1.6);
    }
    const g = pointGeo(p, seed, size);
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: uniformsFor(ctx.U, {}),
      vertexShader: G + /* glsl */`
        attribute float aSeed, aSize; varying float vLife, vHeat; varying vec3 vQ;
        void main(){
          float sp = 0.22 + 0.30 * fract(aSeed * 13.7);
          float life = fract(uTime * sp + aSeed * 9.0);
          vec3 q = position;
          q.y += life * (7.0 + 16.0 * aSize);
          q.x += 2.4 * life * sin(uTime * 1.3 + aSeed * 31.0) + gustAt(q).x * life * 5.0;
          q.z += 2.4 * life * cos(uTime * 1.1 + aSeed * 17.0) + gustAt(q).y * life * 5.0;
          vLife = life; vQ = q; vHeat = emberAt(vec3(position.x, q.y, position.z));
          vec4 mv = viewMatrix * vec4(q, 1.0);
          gl_PointSize = (1.4 + 2.2 * aSize) * (1.0 - 0.5 * life) * (70.0 / max(-mv.z, 1.0));
          gl_Position = projectionMatrix * mv; }`,
      fragmentShader: G + /* glsl */`
        varying float vLife, vHeat; varying vec3 vQ;
        void main(){
          float a = smoothstep(0.5, 0.0, length(gl_PointCoord - 0.5));
          float flick = 0.55 + 0.45 * sin(uTime * 19.0 + vQ.x * 3.1 + vQ.z * 2.7);
          float f = a * vHeat * flick * (1.0 - smoothstep(0.35, 1.0, vLife));
          vec3 col = mix(vec3(1.0, 0.86, 0.55), uLavaC * 0.7, smoothstep(0.0, 0.8, vLife));
          gl_FragColor = vec4(col * f * 1.4, f * ashAtt(vQ));
        ` + TAIL,
    });
    return addPoints(ctx, g, mat);
  }

  update() { /* every population is uTime/uGust driven in its vertex shader */ }
}

function pointGeo(p, seed, size) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
  g.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
  return g;
}

function addPoints(ctx, g, mat) {
  const pts = new THREE.Points(g, mat);
  pts.frustumCulled = false;
  ctx.scene.add(pts);
  return pts;
}
