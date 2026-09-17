import * as THREE from 'three';
import { crustH, coolAt, BOWL } from '../field.js';
import { scorchMat } from '../materials.js';

/* ═══ COMPONENT: Scorch (the vegetation) ═══
   Almost nothing lives here, and the layer is honest about it: two sparse
   populations, both keyed off coolAt() so nothing is ever growing in a seam.

   Tussocks — wind-burnt scrub, only where the crust has been cold long enough,
   clustered in the lee of old spatter so a few clumps read instead of an even
   sprinkle. Moss mats — sulphur-tolerant crusts, flattened almost to the ground,
   pushed out to the cool margins near the wall foot.

   Both are backlit rather than lit: the seams are BEHIND and BELOW them, so what
   the camera sees is mostly silhouette with an orange rim on the underside of each
   blade. That only works if the silhouette is real, hence the alpha discard in
   FRAG_SCORCH — an undiscarded quad here reads as a rectangle of cardboard lit
   from the wrong side, which is worse than nothing.

   InstancedMesh, not InstancedBufferGeometry: only InstancedMesh makes three.js
   define USE_INSTANCING, which VERT_WORLD needs to see instanceMatrix at all. */
export class Scorch {
  constructor(ctx) {
    this.ctx = ctx;
    this.tuss = this.sow(ctx, 340, {
      rMin: 30, rMax: BOWL - 6, cool: 0.78, clump: 5,
      hMin: 0.75, hMax: 2.05, flat: 1.0,
      tint: (d) => [0.15 + 0.13 * d, 0.145 + 0.010 * d, 0.085 + 0.020 * d],
    });
    this.moss = this.sow(ctx, 260, {
      rMin: 58, rMax: BOWL + 14, cool: 0.62, clump: 8,
      hMin: 0.12, hMax: 0.26, flat: 4.2,
      tint: (d) => [0.15 + 0.10 * d, 0.24 + 0.08 * d, 0.11 + 0.04 * d],
    });
  }

  sow(ctx, N, o) {
    const { rr, rnd } = ctx;
    const geo = crossedBlades();
    const mesh = new THREE.InstancedMesh(geo, scorchMat(ctx), N);
    mesh.frustumCulled = false;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    const tints = new Float32Array(N * 3);
    let n = 0, guard = 0, cx = 0, cz = 0, left = 0;
    while (n < N && guard++ < N * 60) {
      if (left <= 0) {                                   // pick a new clump centre
        const a = rr(0, Math.PI * 2), r = rr(o.rMin, o.rMax);
        cx = Math.cos(a) * r; cz = Math.sin(a) * r;
        if (coolAt(cx, cz) < o.cool) continue;
        left = 1 + Math.floor(rnd() * o.clump);
      }
      const x = cx + rr(-3.2, 3.2), z = cz + rr(-3.2, 3.2);
      left--;
      if (Math.hypot(x, z) > o.rMax + 5) continue;
      if (coolAt(x, z) < o.cool * 0.82) continue;
      const h = rr(o.hMin, o.hMax);
      p.set(x, crustH(x, z) - 0.06, z);
      q.setFromAxisAngle(up, rr(0, Math.PI * 2));
      s.set(h * o.flat * rr(0.7, 1.3), h, h * o.flat * rr(0.7, 1.3));
      mesh.setMatrixAt(n, m.compose(p, q, s));
      const d = rr(0, 1), t = o.tint(d);
      tints[n * 3] = t[0]; tints[n * 3 + 1] = t[1]; tints[n * 3 + 2] = t[2];
      n++;
    }
    mesh.count = n;
    mesh.instanceMatrix.needsUpdate = true;
    geo.setAttribute('aTint', new THREE.InstancedBufferAttribute(tints, 3));
    ctx.scene.add(mesh);
    return mesh;
  }

  update() { /* bend is driven by uGust/uTime inside VERT_SCORCH */ }
}

/* three blades crossed about the vertical, built explicitly so there is no
   dependency on BufferGeometryUtils being present in the assembled bundle. */
function crossedBlades() {
  const g = new THREE.BufferGeometry();
  const pos = [], nor = [], uv = [], idx = [];
  for (let k = 0; k < 3; k++) {
    const a = (k / 3) * Math.PI, ax = Math.cos(a), az = Math.sin(a), o = k * 4;
    pos.push(-0.5 * ax, 0, -0.5 * az, 0.5 * ax, 0, 0.5 * az, 0.5 * ax, 1, 0.5 * az, -0.5 * ax, 1, -0.5 * az);
    for (let i = 0; i < 4; i++) nor.push(-az, 0.3, ax);
    uv.push(0, 0, 1, 0, 1, 1, 0, 1);
    idx.push(o, o + 1, o + 2, o, o + 2, o + 3);
  }
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}
