import * as THREE from 'three';
import { canyonH, inSlot, LEN, meander, halfWidth } from '../field.js';
import { scrubMat } from '../materials.js';

/* ═══ COMPONENT: Scrub (the vegetation) ═══
   Hardy desert brush: sparse on the open floor, clustered where runoff collects
   against the wall feet. Instanced crossed quads — cheap, and enough to read as
   brush at the camera's distance. Sways with uWind through VERT_SCRUB.

   InstancedMesh, not InstancedBufferGeometry: only InstancedMesh makes three.js
   define USE_INSTANCING, which VERT_WORLD needs to see instanceMatrix at all. */
export class Scrub {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr, rnd } = ctx;
    const N = 1100;

    const geo = crossedQuads();
    this.mesh = new THREE.InstancedMesh(geo, scrubMat(ctx), N);
    this.mesh.frustumCulled = false;

    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    const cols = new Float32Array(N * 3);
    let n = 0, guard = 0;
    while (n < N && guard++ < N * 40) {
      const z = rr(-LEN / 2 + 6, LEN / 2 - 6);
      const hw = halfWidth(z);
      // bias toward the wall feet, where the little water there is collects
      const edge = rnd() < 0.62 ? (rnd() < 0.5 ? -1 : 1) * rr(0.55, 0.98) : rr(-0.5, 0.5);
      const x = meander(z) + edge * hw;
      if (!inSlot(x, z)) continue;
      const h = rr(0.35, 1.15);
      p.set(x, canyonH(x, z) - 0.05, z);
      q.setFromAxisAngle(up, rr(0, Math.PI * 2));
      s.set(h * rr(0.7, 1.2), h, h * rr(0.7, 1.2));
      this.mesh.setMatrixAt(n, m.compose(p, q, s));
      const dry = rr(0, 1);
      cols[n * 3] = 0.26 + 0.32 * dry;
      cols[n * 3 + 1] = 0.33 - 0.07 * dry;
      cols[n * 3 + 2] = 0.15 + 0.06 * dry;
      n++;
    }
    this.mesh.count = n;
    this.mesh.instanceMatrix.needsUpdate = true;
    geo.setAttribute('aCol', new THREE.InstancedBufferAttribute(cols, 3));
    ctx.scene.add(this.mesh);
  }
  update() { /* sway is driven by uWind/uTime inside VERT_SCRUB */ }
}

/* two quads crossed at right angles, built explicitly so there is no dependency
   on BufferGeometryUtils being present in the assembled bundle. */
function crossedQuads() {
  const g = new THREE.BufferGeometry();
  const pos = [], nor = [], uv = [], idx = [];
  const blades = [
    { ax: 1, az: 0, nx: 0, nz: 1 },
    { ax: 0, az: 1, nx: 1, nz: 0 },
  ];
  blades.forEach((b, k) => {
    const o = k * 4;
    pos.push(-0.5 * b.ax, 0, -0.5 * b.az,
              0.5 * b.ax, 0,  0.5 * b.az,
              0.5 * b.ax, 1,  0.5 * b.az,
             -0.5 * b.ax, 1, -0.5 * b.az);
    for (let i = 0; i < 4; i++) nor.push(b.nx, 0.35, b.nz);
    uv.push(0, 0, 1, 0, 1, 1, 0, 1);
    idx.push(o, o + 1, o + 2, o, o + 2, o + 3);
  });
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}
