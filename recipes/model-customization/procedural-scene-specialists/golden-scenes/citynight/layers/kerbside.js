import * as THREE from 'three';
import { streetH, UP, BLOCK, KERB_X, FACE_X } from '../field.js';
import { sprigMat, brickMat } from '../materials.js';

/* ═══ COMPONENT: Kerbside (the vegetation) ═══
   What actually grows on a street: a thin file of pollarded street trees in their
   pits, and weeds in the gutter joints and along the wall feet. Sparse and scruffy
   on purpose — this is not a forest, and a dense canopy here would hide the very
   lights the world is about.

   One InstancedMesh of crossed quads carries both, with aSprig.y selecting which
   silhouette FRAG_SPRIG carves; a second carries the trunks. InstancedMesh, not
   InstancedBufferGeometry: only InstancedMesh makes three.js define USE_INSTANCING,
   which VERT_WORLD needs to see instanceMatrix at all. */
export class Kerbside {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr, rnd } = ctx;

    const tufts = [];            // crossed-quad instances: canopy clusters + weeds
    const trunks = [];

    // street trees: one every ~20 m, alternating pavements, set back from the kerb
    for (let z = -BLOCK / 2 + 8; z < BLOCK / 2 - 8; z += rr(11, 17)) {
      const side = rnd() < 0.5 ? -1 : 1;
      const x = side * (KERB_X + 1.6 + rr(-0.3, 0.3));
      const base = streetH(x, z) - 0.05;
      const th = rr(3.4, 5.1);
      trunks.push({ x, y: base, z, h: th, r: rr(0.09, 0.15) });
      const clumps = 3 + Math.floor(rnd() * 3);
      for (let c = 0; c < clumps; c++) {
        const s = rr(2.1, 3.4);
        tufts.push({
          x: x + rr(-0.8, 0.8), y: base + th * rr(0.62, 0.95), z: z + rr(-0.8, 0.8),
          sx: s, sy: s * rr(0.8, 1.15), rot: rr(0, Math.PI),
          kind: 1, ragged: rr(0, 1), seed: rnd(),
          col: [0.075 + 0.07 * rnd(), 0.150 + 0.11 * rnd(), 0.070 + 0.06 * rnd()],
        });
      }
    }

    // weeds: the gutter joint and the foot of the frontage, where grit collects
    for (let i = 0; i < 400; i++) {
      const side = rnd() < 0.5 ? -1 : 1;
      const gutter = rnd() < 0.78;
      const x = side * (gutter ? KERB_X - rr(0.1, 0.55) : rr(FACE_X - 0.9, FACE_X - 0.15));
      const z = rr(-BLOCK / 2, BLOCK / 2);
      const s = gutter ? rr(0.24, 0.62) : rr(0.16, 0.38);
      tufts.push({
        x, y: streetH(x, z) - 0.03, z, sx: s * rr(0.8, 1.3), sy: s, rot: rr(0, Math.PI),
        kind: 0, ragged: rr(0, 1), seed: rnd(),
        col: [0.10 + 0.10 * rnd(), 0.15 + 0.13 * rnd(), 0.06 + 0.05 * rnd()],
      });
    }

    const geo = crossedQuads();
    this.tufts = new THREE.InstancedMesh(geo, sprigMat(ctx), tufts.length);
    this.tufts.frustumCulled = false;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s3 = new THREE.Vector3();
    const aTuft = new Float32Array(tufts.length * 3), aSprig = new Float32Array(tufts.length * 3);
    tufts.forEach((t, i) => {
      p.set(t.x, t.y, t.z); q.setFromAxisAngle(UP, t.rot); s3.set(t.sx, t.sy, t.sx);
      this.tufts.setMatrixAt(i, m.compose(p, q, s3));
      aTuft.set(t.col, i * 3);
      aSprig[i * 3] = t.seed; aSprig[i * 3 + 1] = t.kind; aSprig[i * 3 + 2] = t.ragged;
    });
    this.tufts.instanceMatrix.needsUpdate = true;
    geo.setAttribute('aTuft', new THREE.InstancedBufferAttribute(aTuft, 3));
    geo.setAttribute('aSprig', new THREE.InstancedBufferAttribute(aSprig, 3));
    ctx.scene.add(this.tufts);

    const tg = new THREE.CylinderGeometry(0.62, 1.0, 1, 7, 1, true);
    tg.translate(0, 0.5, 0);
    this.trunks = new THREE.InstancedMesh(tg, brickMat(ctx, [0.10, 0.085, 0.07], { pane: 0, side: THREE.DoubleSide }), trunks.length);
    this.trunks.frustumCulled = false;
    trunks.forEach((t, i) => {
      p.set(t.x, t.y, t.z); q.identity(); s3.set(t.r, t.h, t.r);
      this.trunks.setMatrixAt(i, m.compose(p, q, s3));
    });
    this.trunks.instanceMatrix.needsUpdate = true;
    ctx.scene.add(this.trunks);
  }
  update() { /* sway is driven by uGust/uTime inside VERT_SPRIG */ }
}

/* two quads crossed at right angles, built explicitly so there is no dependency on
   BufferGeometryUtils being present in the assembled bundle. */
function crossedQuads() {
  const g = new THREE.BufferGeometry();
  const pos = [], nor = [], uv = [], idx = [];
  [{ ax: 1, az: 0, nx: 0, nz: 1 }, { ax: 0, az: 1, nx: 1, nz: 0 }].forEach((b, k) => {
    const o = k * 4;
    pos.push(-0.5 * b.ax, 0, -0.5 * b.az, 0.5 * b.ax, 0, 0.5 * b.az,
             0.5 * b.ax, 1, 0.5 * b.az, -0.5 * b.ax, 1, -0.5 * b.az);
    for (let i = 0; i < 4; i++) nor.push(b.nx, 0.4, b.nz);
    uv.push(0, 0, 1, 0, 1, 1, 0, 1);
    idx.push(o, o + 1, o + 2, o, o + 2, o + 3);
  });
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}
