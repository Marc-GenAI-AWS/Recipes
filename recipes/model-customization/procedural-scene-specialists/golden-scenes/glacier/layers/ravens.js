import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { iceH, flowline, BASIN, MEDIAL } from '../field.js';

/* ═══ COMPONENT: Ravens (the fauna) ═══
   Alpine choughs and ravens are the only large animals that work a glacier: they
   ride the wind off the headwall, cut across the basin, and drop onto the medial
   moraine to pick at whatever the ice gave up. Black on snow is the strongest
   contrast in the frame, so they are what the eye finds first — they have to move
   like birds or the whole scene goes to plastic.

   Wings actually beat: aPh/aRate/aAmp per instance drive a flap in the vertex
   shader that bends the wing along |x|, so a bird is never a rigid glyph. The
   perched ones keep their wings folded and shuffle instead.

   Scale matters — a raven is ~1.3 units across at the wing, seen from 15-60 units
   away. Bigger and the basin stops reading as kilometres wide. */
export class Ravens {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr, rnd } = ctx;
    const FLY = 11, PERCH = 5, N = FLY + PERCH;

    this.birds = [];
    for (let i = 0; i < FLY; i++) {
      this.birds.push({
        perched: false,
        cx: rr(-24, 32), cz: rr(-40, 90),
        r: rr(9, 30), y: rr(5, 22),
        w: rr(0.09, 0.20) * (rnd() < 0.5 ? -1 : 1),
        ph: rr(0, Math.PI * 2), span: rr(1.5, 2.2),
      });
    }
    for (let i = 0; i < PERCH; i++) {
      const z = rr(20, 84);
      const x = flowline(z) + MEDIAL + rr(-2.2, 2.2);
      this.birds.push({ perched: true, x, z, y: iceH(x, z) + 0.22, ph: rr(0, Math.PI * 2), span: rr(1.3, 1.7) });
    }

    const geo = ravenGeometry();
    const ph = new Float32Array(N), rate = new Float32Array(N), amp = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      ph[i] = this.birds[i].ph;
      rate[i] = this.birds[i].perched ? rr(0.4, 0.9) : rr(4.0, 6.2);
      amp[i] = this.birds[i].perched ? 0.04 : rr(0.42, 0.72);
    }
    geo.setAttribute('aPh', new THREE.InstancedBufferAttribute(ph, 1));
    geo.setAttribute('aRate', new THREE.InstancedBufferAttribute(rate, 1));
    geo.setAttribute('aAmp', new THREE.InstancedBufferAttribute(amp, 1));

    this.mesh = new THREE.InstancedMesh(geo, ravenMat(ctx), N);
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);

    this.m = new THREE.Matrix4(); this.q = new THREE.Quaternion();
    this.p = new THREE.Vector3(); this.s = new THREE.Vector3(); this.e = new THREE.Euler();
  }

  update(dt, t) {
    const { m, q, p, s, e } = this;
    const sp = this.ctx.cur ? (this.ctx.cur.ravenSpeed ?? 1) : 1;
    for (let i = 0; i < this.birds.length; i++) {
      const b = this.birds[i];
      if (b.perched) {
        // a shuffle and a turn of the head: enough to read as alive, not as a prop
        p.set(b.x + 0.16 * Math.sin(t * 0.6 * sp + b.ph), b.y + 0.05 * Math.abs(Math.sin(t * 1.4 * sp + b.ph)), b.z);
        e.set(0, b.ph + 0.5 * Math.sin(t * 0.35 * sp + b.ph), 0, 'YXZ');
      } else {
        const a = b.ph + t * b.w * sp;
        const x = b.cx + Math.cos(a) * b.r + 6.0 * Math.sin(t * 0.13 * sp + b.ph);
        const z = b.cz + Math.sin(a) * b.r * 1.35;
        const y = Math.max(b.y + 3.0 * Math.sin(t * 0.19 * sp + b.ph * 2.0), iceH(x, z) + 2.5);
        p.set(x, y, z);
        const heading = a + (b.w > 0 ? Math.PI / 2 : -Math.PI / 2);
        e.set(0.10 * Math.sin(t * 0.5 + b.ph), heading, b.w > 0 ? -0.36 : 0.36, 'YXZ');
      }
      q.setFromEuler(e);
      s.setScalar(b.span);
      this.mesh.setMatrixAt(i, m.compose(p, q, s));
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}

/* a raven in plan: blunt head, deep body, broad fingered wings and the wedge tail
   that tells a raven from a crow. Flat, because a bird over snow is read from its
   outline long before any of its shading. */
function ravenGeometry() {
  const g = new THREE.BufferGeometry();
  const pos = [
    0, 0, -0.46, 0, 0, 0.34,                      // 0 head   1 tail root
    0, 0, 0.62, -0.13, 0, 0.56, 0.13, 0, 0.56,    // 2 tail tip  3,4 tail corners
    -0.16, 0, -0.06, 0.16, 0, -0.06,              // 5,6 shoulders
    -0.46, 0.03, 0.02, -0.50, 0.04, 0.20,         // 7,8 left wing leading/trailing
    0.46, 0.03, 0.02, 0.50, 0.04, 0.20,           // 9,10 right
  ];
  const idx = [
    0, 5, 1, 0, 1, 6,            // body
    1, 3, 2, 1, 2, 4,            // wedge tail
    5, 7, 8, 5, 8, 1,            // left wing
    6, 1, 10, 6, 10, 9,          // right wing
  ];
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

const ravenMat = (ctx) => new THREE.ShaderMaterial({
  side: THREE.DoubleSide,
  uniforms: uniformsFor(ctx.U, { uFeatherC: F(new THREE.Color(0.045, 0.048, 0.062)) }),
  vertexShader: /* glsl */`
    varying vec3 vP, vN; uniform float uTime;
    attribute float aPh; attribute float aRate; attribute float aAmp;
    void main(){
      #ifdef USE_INSTANCING
      mat4 m = modelMatrix * instanceMatrix;
      #else
      mat4 m = modelMatrix;
      #endif
      vec3 q = position;
      /* the beat: wings bend up and down along their length, and sweep back a
         little at the top of the stroke */
      float beat = sin(uTime * aRate + aPh);
      float r = abs(q.x);
      q.y += beat * aAmp * pow(r, 1.6) * 2.2;
      q.z += (0.5 - 0.5 * beat) * aAmp * r * 0.35;
      vec4 wp = m * vec4(q, 1.0);
      vP = wp.xyz; vN = normalize(mat3(m) * normal);
      gl_Position = projectionMatrix * viewMatrix * wp; }`,
  fragmentShader: G + /* glsl */`
    varying vec3 vP, vN; uniform vec3 uFeatherC;
    void main(){
      vec3 n = normalize(vN);
      float lam = max(dot(n, -uSolarV), 0.0);
      /* the glacier lights this bird from underneath: black feathers over snow pick
         up a hard blue-white rim from upwash, which is what stops it reading as a
         hole cut in the frame */
      vec3 col = uFeatherC * (0.55 + 2.4 * uDomeI * 0.25 + 1.6 * lam * uSolarI)
               + upwash(vP, n) * 0.85
               + uDomeC * uDomeI * 0.12 * max(n.y, 0.0)
               + uSolarC * uSolarI * pow(lam, 22.0) * 0.30;      /* gloss on the wing coverts */
      gl_FragColor = vec4(aerial(col, vP), 1.0);
    ` + TAIL,
});
