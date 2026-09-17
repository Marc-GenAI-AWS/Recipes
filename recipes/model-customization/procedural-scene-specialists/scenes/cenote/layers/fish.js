import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { floorH } from '../field.js';

/* ═══ COMPONENT: Fish ═══
   One instanced fish mesh (fusiform body, forked tail, dorsal/anal/pectoral
   fins), body-wave swimming, banking school that flashes in the beam. Three
   species: silver school in the pillar, orange reef fish, big dark bottom fish. */
export class Fish {
  constructor(ctx) {
    const { scene, U, rnd, rr } = ctx;
    this.ctx = ctx;
    /* body: a sphere pulled into a fusiform profile; fins: hand-placed triangles tagged by aFin (1 tail, 2 dorsal/anal, 3 pectoral) */
    const body = new THREE.SphereGeometry(1, 28, 14).toNonIndexed(), bp = body.attributes.position;
    for (let i = 0; i < bp.count; i++) {
      const x = bp.getX(i), t = (x + 1) / 2, H = Math.max(0.07, 0.36 * Math.pow(Math.sin(Math.PI * Math.pow(t, 0.72)), 0.8)), W = H * (0.4 + 0.25 * (1 - t));
      bp.setXYZ(i, x > 0.4 ? 0.4 + (x - 0.4) * 0.7 : x, bp.getY(i) * (H + 0.05 * Math.max(0, t - 0.8) * 5), bp.getZ(i) * W);   /* shorter, blunter snout */
    }
    const fins = [[-0.98, 0.03, 0, -1.55, 0.46, 0, -1.22, 0, 0], [-0.98, -0.03, 0, -1.22, 0, 0, -1.55, -0.46, 0],       /* forked tail */
      [0.45, 0.2, 0, 0.05, 0.5, 0, -0.35, 0.16, 0], [-0.05, -0.2, 0, -0.3, -0.38, 0, -0.5, -0.13, 0],                       /* dorsal, anal */
      [0.35, -0.04, 0.12, 0.05, -0.14, 0.42, 0.18, -0.2, 0.2], [0.35, -0.04, -0.12, 0.05, -0.14, -0.42, 0.18, -0.2, -0.2]];  /* pectorals */
    const nB = bp.count, pos = new Float32Array((nB + 18) * 3), fin = new Float32Array(nB + 18);
    pos.set(bp.array); fins.forEach((f, k) => { pos.set(f, (nB + k * 3) * 3); fin.fill(k < 2 ? 1 : k < 4 ? 2 : 3, nB + k * 3, nB + k * 3 + 3); });
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aFin', new THREE.BufferAttribute(fin, 1)); g.computeVertexNormals();
    /* three species: silver school in the pillar, orange reef fish over the coral, big dark bottom fish */
    this.N = 190; const phase = new Float32Array(this.N), tone = new Float32Array(this.N); this.fish = [];
    for (let i = 0; i < this.N; i++) {
      const kind = i < 3 ? 2 : i < 45 ? 1 : 0, r = kind ? rr(3, 14) : rr(2.0, 6.5), a0 = rnd() * 6.283;
      const f = { kind, r, a: a0, w: (kind === 2 ? 0.06 : rr(0.2, 0.4)) * (rnd() < 0.1 ? -1 : 1), ph: rnd() * 6.283, ph2: rnd() * 6.283,
        s: kind === 2 ? rr(1.4, 2.0) : kind === 1 ? rr(0.2, 0.34) : rr(0.26, 0.5), y: kind === 2 ? rr(-13.5, -11.5) : rr(-9, -2.5),
        hx: Math.cos(a0) * r, hz: Math.sin(a0) * r };
      if (kind === 1) f.hy = floorH(f.hx, f.hz) + rr(0.7, 2.4);
      this.fish.push(f); phase[i] = rnd() * 6.283; tone[i] = kind === 2 ? rr(0.75, 1) : kind === 1 ? rr(0.4, 0.65) : rnd() * 0.3;
    }
    g.setAttribute('aPhase', new THREE.InstancedBufferAttribute(phase, 1)); g.setAttribute('aTone', new THREE.InstancedBufferAttribute(tone, 1));
    this.mesh = new THREE.InstancedMesh(g, new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, { uFishSpeed: U.uFishSpeed }), side: THREE.DoubleSide,
      vertexShader: /* glsl */`
      attribute float aPhase, aTone, aFin; varying vec3 vP, vN, vL; varying float vTone, vFin; uniform float uTime, uFishSpeed;
      void main(){ vec3 p = position; float ph = uTime * (5.0 + 4.0 * uFishSpeed) * (1.35 - aTone) + aPhase;
        float env = smoothstep(0.6, -1.5, p.x); env *= env;                         /* body wave grows toward the tail */
        p.z += sin(ph - p.x * 2.2) * (0.02 + 0.3 * env) * (0.45 + 0.55 * uFishSpeed);
        if (aFin > 2.5) { p.z += sign(p.z) * 0.1 * sin(ph * 0.5 + 1.0) * p.z * p.z * 5.0; p.y += 0.05 * sin(ph * 0.5); }   /* pectoral flap */
        mat4 m = modelMatrix * instanceMatrix; vec4 wp = m * vec4(p, 1.0); vP = wp.xyz; vN = normalize(mat3(m) * normal); vL = p; vTone = aTone; vFin = aFin;
        gl_Position = projectionMatrix * viewMatrix * wp; }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP, vN, vL; varying float vTone, vFin;
      void main(){ vec3 n = normalize(vN); if (!gl_FrontFacing) n = -n; vec3 V = normalize(cameraPosition - vP); float bm = beamMask(vP);
        vec3 back = vec3(0.10, 0.14, 0.2), belly = vec3(0.8, 0.84, 0.86); float bar = 0.0;
        if (vTone > 0.7) { back = vec3(0.15, 0.14, 0.09); belly = vec3(0.42, 0.4, 0.3); }
        else if (vTone > 0.35) { back = vec3(0.95, 0.42, 0.1); belly = vec3(1.0, 0.78, 0.4); bar = smoothstep(0.1, 0.05, abs(vL.x - 0.1)); }
        vec3 base = mix(belly, back, smoothstep(-0.1, 0.12, vL.y)); base = mix(base, vec3(0.95), bar * 0.85);
        base *= 1.0 - 0.35 * exp(-pow((vL.y - 0.02) * 28.0, 2.0)) * step(vFin, 0.5);                           /* lateral line */
        float de = length(vL.xy - vec2(0.64, 0.05)); base = mix(base, vec3(0.9), smoothstep(0.075, 0.062, de) * step(vFin, 0.5));
        base = mix(base, vec3(0.03), smoothstep(0.055, 0.04, de) * step(vFin, 0.5));                            /* eye */
        if (vFin > 0.5) base = mix(base, belly, 0.5) * 0.85;                                                     /* membrane fins */
        vec3 L = -uSunDir, H = normalize(L + V); float lam = max(dot(n, L), 0.0), spec = pow(max(dot(n, H), 0.0), 40.0) * (0.3 + 3.0 * bm);
        vec3 irid = mix(vec3(0.7, 0.9, 1.0), vec3(1.0, 0.85, 0.7), 0.5 + 0.5 * sin(dot(n, V) * 8.0 + vL.x * 3.0));
        vec3 light = uAmbC * uAmbI * 0.6 + uSunC * uSunI * lam * (0.12 + 0.88 * bm) + torch(vP, n);
        vec3 col = base * light + uSunC * uSunI * spec * 0.8 * irid * (1.0 - step(0.7, vTone)) + pow(1.0 - max(dot(n, V), 0.0), 3.0) * uAmbC * uAmbI * 0.6;
        gl_FragColor = vec4(fog(col, vP), 1.0);` + TAIL }), this.N);
    scene.add(this.mesh); this.d = new THREE.Object3D(); this.X = new THREE.Vector3(1, 0, 0); this.h = new THREE.Vector3(); this.q = new THREE.Quaternion(); this.roll = new THREE.Quaternion();
  }
  pos(f, a, t, out) {
    if (f.kind === 1) return out.set(f.hx + 0.7 * Math.sin(t * 0.9 + f.ph), f.hy + 0.25 * Math.sin(t * 1.3 + f.ph2), f.hz + 0.7 * Math.cos(t * 0.7 + f.ph));
    const c = f.kind === 2 ? 0 : 1;
    return out.set(Math.cos(a) * f.r + 2.6 * c * Math.sin(t * 0.05), f.y + 0.35 * f.r * Math.sin(2 * a + f.ph) * c + 1.4 * c * Math.sin(t * 0.07 + f.ph) + 0.3 * Math.sin(t * 0.9 + f.ph), Math.sin(a) * f.r + 2.0 * c * Math.cos(t * 0.04));
  }
  update(dt, t) {
    const cur = this.ctx.cur, sp = cur.fishSpeed, N = this.N, d = this.d, p2 = this.h;
    for (let i = 0; i < N; i++) {
      const f = this.fish[i]; f.a += f.w * sp * dt; this.pos(f, f.a, t, d.position); this.pos(f, f.a + 0.02 * Math.sign(f.w), t + 0.02, p2);
      p2.sub(d.position); if (p2.lengthSq() > 1e-8) this.q.setFromUnitVectors(this.X, p2.normalize());
      const bank = f.kind === 0 ? -0.4 * Math.sign(f.w) + 0.35 * Math.sin(t * 0.35 + i * 0.03) : 0.1 * Math.sin(t * 0.5 + f.ph);   /* bank into the turn; a roll ripples through the school */
      d.quaternion.copy(this.q).multiply(this.roll.setFromAxisAngle(this.X, bank));
      const vis = f.kind === 2 ? 1 : THREE.MathUtils.clamp((cur.fishFrac * N - i) * 0.5, 0, 1); d.scale.setScalar(f.s * vis); d.updateMatrix(); this.mesh.setMatrixAt(i, d.matrix);
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}
