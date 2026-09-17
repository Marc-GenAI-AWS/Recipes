import * as THREE from 'three';
import { iceH, flowline, onRock, BASIN, EDGE, MEDIAL } from '../field.js';
import { crustMat } from '../materials.js';

/* ═══ COMPONENT: Lichen (the vegetation) ═══
   Almost nothing lives at this altitude, and the layer is sparse by design — there
   is no turf to lay down. What there is grows on rock the ice has uncovered: map
   lichen and rusty crustose scabs flat on the moraine blocks, and a few cushions of
   hardy moss in the lee of the bigger stones, where meltwater runs and the katabatic
   wind is broken.

   Two populations from one crossed-quad geometry: crusts laid almost flat and wide,
   cushions standing up. Both carve their silhouette with an alpha discard in
   FRAG_CRUST — a quad is a rectangle, and a rectangle of green on grey rock reads
   as a sticker, not a plant.

   InstancedMesh, not InstancedBufferGeometry: only InstancedMesh makes three.js
   define USE_INSTANCING, which VERT_WORLD needs to see instanceMatrix at all. */
export class Lichen {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr, rnd } = ctx;
    const N = 620;

    const geo = crossedQuads();
    this.mesh = new THREE.InstancedMesh(geo, crustMat(ctx), N);
    this.mesh.frustumCulled = false;

    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    const p = new THREE.Vector3(), s = new THREE.Vector3();
    const tint = new Float32Array(N * 3);
    let n = 0, guard = 0;
    while (n < N && guard++ < N * 30) {
      // two thirds on the medial moraine the camera walks beside, the rest out on
      // the lateral moraine where the rock band is wide
      let x, z;
      if (rnd() < 0.72) {
        z = rr(-38, BASIN / 2 - 8);
        x = flowline(z) + MEDIAL + rr(-2.6, 2.6);
      } else {
        z = rr(-BASIN / 2 + 76, BASIN / 2 - 8);
        x = flowline(z) + (rnd() < 0.5 ? -1 : 1) * (EDGE + rr(3.0, 16));
        if (!onRock(x, z)) continue;
        // only on ground flat enough to hold it — on the steep moraine faces a quad
        // laid on the height field pokes out of the rock and reads as floating litter
        if (Math.abs(iceH(x + 1.5, z) - iceH(x - 1.5, z)) > 2.4) continue;
      }
      const crust = rnd() < 0.68;
      const h = crust ? rr(0.06, 0.14) : rr(0.22, 0.50);
      p.set(x, iceH(x, z) - 0.04, z);
      // crusts lie back against the stone they are eating; cushions stand upright
      e.set(crust ? rr(1.05, 1.42) : rr(-0.12, 0.12), rr(0, Math.PI * 2), rr(-0.2, 0.2), 'YXZ');
      q.setFromEuler(e);
      const w = crust ? rr(0.55, 1.45) : rr(0.35, 0.65);
      s.set(w, h * (crust ? 5.0 : 1.0), w);
      this.mesh.setMatrixAt(n, m.compose(p, q, s));
      const k = rr(0, 1);
      if (crust) {                                  // map lichen: rust and pale sage,
        if (rnd() < 0.5) {                          // never the sulphur yellow of a
          tint[n * 3] = 0.30 + 0.20 * k;            // pot of paint
          tint[n * 3 + 1] = 0.17 + 0.10 * k;
          tint[n * 3 + 2] = 0.08 + 0.05 * k;
        } else {
          tint[n * 3] = 0.31 + 0.14 * k;
          tint[n * 3 + 1] = 0.34 + 0.14 * k;
          tint[n * 3 + 2] = 0.20 + 0.08 * k;
        }
      } else {                                      // moss cushion: dark olive
        tint[n * 3] = 0.13 + 0.09 * k;
        tint[n * 3 + 1] = 0.21 + 0.11 * k;
        tint[n * 3 + 2] = 0.09 + 0.05 * k;
      }
      n++;
    }
    this.mesh.count = n;
    this.mesh.instanceMatrix.needsUpdate = true;
    geo.setAttribute('aTint', new THREE.InstancedBufferAttribute(tint, 3));
    ctx.scene.add(this.mesh);
  }
  update() { /* the cushions' flex is driven by uGustV/uTime inside VERT_CRUST */ }
}

/* two quads crossed at right angles, built explicitly so there is no dependency on
   BufferGeometryUtils being present in the assembled bundle. */
function crossedQuads() {
  const g = new THREE.BufferGeometry();
  const pos = [], nor = [], uv = [], idx = [];
  const blades = [{ ax: 1, az: 0, nx: 0, nz: 1 }, { ax: 0, az: 1, nx: 1, nz: 0 }];
  blades.forEach((b, k) => {
    const o = k * 4;
    pos.push(-0.5 * b.ax, 0, -0.5 * b.az, 0.5 * b.ax, 0, 0.5 * b.az,
             0.5 * b.ax, 1, 0.5 * b.az, -0.5 * b.ax, 1, -0.5 * b.az);
    for (let i = 0; i < 4; i++) nor.push(b.nx, 0.5, b.nz);
    uv.push(0, 0, 1, 0, 1, 1, 0, 1);
    idx.push(o, o + 1, o + 2, o, o + 2, o + 3);
  });
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}
