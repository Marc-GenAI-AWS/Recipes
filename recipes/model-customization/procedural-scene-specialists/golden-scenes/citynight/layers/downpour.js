import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { brickMat } from '../materials.js';
import { FIXTURES, NLAMP, BLOCK, KERB_X } from '../field.js';

/* ═══ COMPONENT: Downpour (the effects layer) ═══
   Rain, and the glow the rain puts around everything that is lit. This layer owns
   every artificial source in the world: the fixtures themselves (sodium lamps on
   their brackets, vertical neon, lit shopfronts, a car's headlights), the halo each
   one wears in the wet air, and the shower falling through them.

   It also PUBLISHES the emitter array. There are more fixtures in the street than
   the NLAMP slots the shaders read, so every frame this layer chooses the nearest
   ones and writes uEmiP/uEmiC/uEmiI. That array is what stands in for a sun here:
   the road, the frontages, the trees and the people all shade against it. */
export class Downpour {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr } = ctx;
    const box = new THREE.BoxGeometry(1, 1, 1);

    // ── the dark half of the fixtures: columns and brackets ──
    const posts = [];
    for (const f of FIXTURES) {
      if (f.kind !== 0) continue;
      posts.push({ x: f.postX, y: 3.2, z: f.z, s: [0.16, 6.4, 0.16] });
      posts.push({ x: (f.postX + f.x) / 2, y: 6.34, z: f.z, s: [Math.abs(f.postX - f.x) + 0.2, 0.13, 0.13] });
    }
    this.posts = new THREE.InstancedMesh(box, brickMat(ctx, [0.055, 0.052, 0.058], { pane: 0 }), posts.length);
    this.posts.frustumCulled = false;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s3 = new THREE.Vector3();
    posts.forEach((b, i) => { p.set(b.x, b.y, b.z); s3.set(...b.s); this.posts.setMatrixAt(i, m.compose(p, q, s3)); });
    this.posts.instanceMatrix.needsUpdate = true;
    ctx.scene.add(this.posts);

    // ── the bright half: the lit bodies themselves ──
    const lbox = new THREE.BoxGeometry(1, 1, 1);
    this.lamps = new THREE.InstancedMesh(lbox, lampMat(ctx), FIXTURES.length);
    this.lamps.frustumCulled = false;
    const aLit = new Float32Array(FIXTURES.length * 3);
    FIXTURES.forEach((f, i) => {
      p.set(f.x, f.y, f.z); s3.set(f.sx, f.sy, f.sz);
      this.lamps.setMatrixAt(i, m.compose(p, q, s3));
      aLit[i * 3] = f.c[0] * f.i; aLit[i * 3 + 1] = f.c[1] * f.i; aLit[i * 3 + 2] = f.c[2] * f.i;
    });
    this.lamps.instanceMatrix.needsUpdate = true;
    lbox.setAttribute('aLit', new THREE.InstancedBufferAttribute(aLit, 3));
    ctx.scene.add(this.lamps);

    // ── one car working the far lane, for a pair of moving headlights ──
    this.car = new THREE.Group();
    const dark = brickMat(ctx, [0.045, 0.048, 0.055], { pane: 0 });
    const body = new THREE.Mesh(new THREE.BoxGeometry(1.86, 0.78, 4.4), dark); body.position.y = 0.62;
    const cab = new THREE.Mesh(new THREE.BoxGeometry(1.62, 0.66, 2.1), dark); cab.position.set(0, 1.28, -0.25);
    this.car.add(body, cab);
    this.car.position.set(KERB_X * 0.5, 0, -75);
    ctx.scene.add(this.car);

    // ── the halo each source wears: one billboard per emitter slot ──
    const hg = new THREE.PlaneGeometry(1, 1);
    this.halos = new THREE.InstancedMesh(hg, haloMat(ctx), NLAMP);
    this.halos.frustumCulled = false;
    this.aHalo = new Float32Array(NLAMP * 3);
    hg.setAttribute('aHalo', new THREE.InstancedBufferAttribute(this.aHalo, 3));
    ctx.scene.add(this.halos);

    // ── the shower: short streaks in a box that travels with the camera ──
    const RN = 3600;
    const rp = new Float32Array(RN * 6), rs = new Float32Array(RN * 2), re = new Float32Array(RN * 2);
    for (let i = 0; i < RN; i++) {
      const x = rr(-20, 20), y = rr(-15, 15), z = rr(-23, 23), sd = rr(0, 1);
      for (let k = 0; k < 2; k++) {
        rp[i * 6 + k * 3] = x; rp[i * 6 + k * 3 + 1] = y; rp[i * 6 + k * 3 + 2] = z;
        rs[i * 2 + k] = sd; re[i * 2 + k] = k;
      }
    }
    const rg = new THREE.BufferGeometry();
    rg.setAttribute('position', new THREE.BufferAttribute(rp, 3));
    rg.setAttribute('aSeed', new THREE.BufferAttribute(rs, 1));
    rg.setAttribute('aEnd', new THREE.BufferAttribute(re, 1));
    this.rain = new THREE.LineSegments(rg, rainMat(ctx));
    this.rain.frustumCulled = false;
    ctx.scene.add(this.rain);

    this.m = m; this.q = q; this.p = p; this.s3 = s3;
    this.order = FIXTURES.map((_, i) => i);
  }

  update(dt, t) {
    const { U, cur, camera } = this.ctx;
    const { m, q, p, s3 } = this;

    // the car closes with the walk, then wraps back to the far end of the block
    let cz = this.car.position.z + dt * 8.5;
    if (cz > BLOCK / 2) cz -= BLOCK;
    this.car.position.z = cz;

    // choose the NLAMP-2 nearest fixtures; the last two slots are the headlights
    const cp = camera.position;
    this.order.sort((a, b) => d2(FIXTURES[a], cp) - d2(FIXTURES[b], cp));
    const NS = NLAMP - 2;
    for (let k = 0; k < NS; k++) {
      const f = FIXTURES[this.order[k]];
      const gain = f.kind === 0 ? cur.lampI : cur.signI;
      // sodium hums, neon buzzes, and one tube in six is on its way out
      const ph = f.z * 0.7 + f.side;
      const buzz = 1 + 0.05 * Math.sin(t * 31 + ph)
        + (Math.abs(Math.sin(ph * 43.7)) > 0.87 ? 0.5 * Math.sin(t * 7.3 + ph) : 0);
      U.uEmiP.value[k].set(f.x, f.y, f.z);
      U.uEmiC.value[k].setRGB(f.c[0], f.c[1], f.c[2]);
      U.uEmiI.value[k] = (f.kind === 0 ? 26 : 24) * f.i * gain * buzz;
    }
    for (let k = 0; k < 2; k++) {
      U.uEmiP.value[NS + k].set(this.car.position.x + (k ? 0.68 : -0.68), 0.72, cz + 2.15);
      U.uEmiC.value[NS + k].setRGB(1.0, 0.95, 0.86);
      U.uEmiI.value[NS + k] = 20 * cur.carI;
    }

    // halos ride the emitters, nudged toward the camera so they clear their fixture
    for (let k = 0; k < NLAMP; k++) {
      const e = U.uEmiP.value[k], I = U.uEmiI.value[k], c = U.uEmiC.value[k];
      p.copy(e).lerp(cp, 0.03);
      const r = Math.min(11.0, (1.2 + 3.6 * cur.halo) * (0.8 + 0.085 * I));
      s3.set(r, r, r);
      this.halos.setMatrixAt(k, m.compose(p, camera.quaternion, s3));
      const a = Math.min(I, 38) * 0.016;
      this.aHalo[k * 3] = c.r * a; this.aHalo[k * 3 + 1] = c.g * a; this.aHalo[k * 3 + 2] = c.b * a;
    }
    this.halos.instanceMatrix.needsUpdate = true;
    this.halos.geometry.attributes.aHalo.needsUpdate = true;
  }
}

const d2 = (f, c) => (f.x - c.x) ** 2 + (f.y - c.y) ** 2 + (f.z - c.z) ** 2;

/* the lit body of a fixture: flat emissive, so it reads as the source and not as a
   surface that happens to be bright. */
const lampMat = (ctx) => new THREE.ShaderMaterial({
  uniforms: uniformsFor(ctx.U, {}),
  vertexShader: /* glsl */`
    varying vec3 vP, vLit; attribute vec3 aLit;
    void main(){ mat4 mm = modelMatrix * instanceMatrix; vec4 wp = mm * vec4(position, 1.0);
      vP = wp.xyz; vLit = aLit; gl_Position = projectionMatrix * viewMatrix * wp; }`,
  fragmentShader: G + /* glsl */`
    varying vec3 vP, vLit;
    void main(){
      float gain = 0.5 * (uLampI + uSignI);
      /* break the slab into tubes and panes so a sign reads as lettering, not a brick of light */
      float tube = mix(0.30, 1.0, step(0.20, fract(vP.y * 2.6)));
      float pane = mix(0.55, 1.0, step(0.14, fract(vP.z * 1.7)));
      vec3 col = vLit * (0.85 + 0.75 * gain) * tube * pane;
      gl_FragColor = vec4(mix(col, uMurkC * 1.2, 1.0 - murkAtt(vP)), 1.0);
    ` + TAIL,
});

/* the halo: the reason a foggy street reads as foggy. A tight core, a broad
   inverse-square bloom that uHaloR opens right up, and a faint pair of spikes
   where the wet air smears the source across the eye. */
const haloMat = (ctx) => new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  uniforms: uniformsFor(ctx.U, {}),
  vertexShader: /* glsl */`
    varying vec2 vH; varying vec3 vHC, vHP; attribute vec3 aHalo;
    void main(){ mat4 mm = modelMatrix * instanceMatrix; vec4 wp = mm * vec4(position, 1.0);
      vH = uv; vHC = aHalo; vHP = wp.xyz; gl_Position = projectionMatrix * viewMatrix * wp; }`,
  fragmentShader: G + /* glsl */`
    varying vec2 vH; varying vec3 vHC, vHP;
    void main(){
      vec2 d = vH - 0.5; float r = length(d) * 2.0;
      if (r > 1.0) discard;
      float core = exp(-r * r * 26.0);
      /* the exponent must stay well above zero or a wide halo flattens into a disc
         with a visible rim — the give-away that it is a billboard and not glare */
      float bloomR = exp(-r * r * max(2.8, 5.5 - 2.2 * uHaloR));
      float spike = pow(max(0.0, 1.0 - abs(d.x) * 13.0), 3.0) + pow(max(0.0, 1.0 - abs(d.y) * 13.0), 3.0);
      float a = (core * 1.3 + bloomR * (0.22 + 0.55 * uHaloR) + spike * 0.10 * bloomR)
              * (1.0 - smoothstep(0.35, 1.0, r));
      gl_FragColor = vec4(vHC * a * (0.5 + 0.9 * murkAtt(vHP)), 1.0);
    ` + TAIL,
});

/* the shower itself: 1-px streaks, leaning on the gust, brightest where they fall
   through a light. Additive, so rain brightens the air instead of masking it. */
const rainMat = (ctx) => new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  uniforms: uniformsFor(ctx.U, {}),
  vertexShader: G + /* glsl */`
    attribute float aSeed, aEnd; varying vec3 vC; varying vec3 vQ;
    void main(){
      vec3 qq = position;
      vec2 g = gustAt(qq) * 2.2;   /* the shower leans wherever the street is funnelling the wind */
      qq.y -= mod(uTime * (13.0 + 11.0 * aSeed) + aSeed * 57.0, 30.0);
      qq.x += g.x * uTime * 0.9; qq.z += g.y * uTime * 0.9;
      vec3 hb = vec3(20.0, 15.0, 23.0);
      vec3 c = cameraPosition + vec3(0.0, 6.0, -6.0);
      qq = c + mod(qq - c + hb, hb * 2.0) - hb;
      float len = (0.14 + 0.42 * uRainAmt) * (0.5 + 0.9 * aSeed);
      qq += aEnd * vec3(g.x * 0.14, 1.0, g.y * 0.14) * len;
      vQ = qq;
      vec3 toCam = normalize(cameraPosition - qq);
      vC = (uMurkC * 0.75 + neonGlow(qq, toCam) * 0.035) * uRainAmt
           * smoothstep(0.6, 5.0, distance(cameraPosition, qq));
      gl_Position = projectionMatrix * viewMatrix * vec4(qq, 1.0); }`,
  fragmentShader: G + /* glsl */`
    varying vec3 vC; varying vec3 vQ;
    void main(){ gl_FragColor = vec4(vC * murkAtt(vQ), 1.0);
    ` + TAIL,
});
