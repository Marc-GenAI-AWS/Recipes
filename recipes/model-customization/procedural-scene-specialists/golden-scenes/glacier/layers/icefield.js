import * as THREE from 'three';
import { iceH, crevasseT, onIce, flowline, HALF, BASIN, EDGE } from '../field.js';
import { iceMat } from '../materials.js';

/* ═══ COMPONENT: Icefield (the ground) ═══
   One mesh carrying the whole basin: the ice tongue, the crevasse field torn across
   it, the lateral moraine and the headwall behind. Every vertex's y comes from
   iceH(x, z) — the shared height field the lichen, the spindrift and the camera all
   sample, so nothing floats or sinks.

   This is the layer that carries the world's signature. Snow here is not white
   paint: it is a translucent solid. FRAG_ICE puts subsurface() light back out of
   the crevasse walls and upwash() back up into everything facing down, so the slots
   read as cyan lamps sunk in the surface rather than as black cracks. */
export class Icefield {
  constructor(ctx) {
    this.ctx = ctx;
    const g = new THREE.PlaneGeometry(HALF * 2, BASIN, 224, 356);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) pos.setY(i, iceH(pos.getX(i), pos.getZ(i)));
    pos.needsUpdate = true;
    g.computeVertexNormals();

    this.mesh = new THREE.Mesh(g, iceMat(ctx, { grit: 1.0, bare: 0.28 }));
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);

    // Seracs: the ice tower blocks left standing between crevasses where the glacier
    // breaks over a step. Bare blue ice, so they glow where the sun goes through them.
    const { rr, rnd } = ctx;
    const N = 110;
    this.seracs = new THREE.InstancedMesh(serac(), iceMat(ctx, { grit: 0.35, bare: 0.92, rocky: 0.0 }), N);
    this.seracs.frustumCulled = false;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    const p = new THREE.Vector3(), s = new THREE.Vector3();
    let n = 0, guard = 0;
    while (n < N && guard++ < N * 60) {
      const z = rr(-BASIN / 2 + 70, BASIN / 2 - 10);
      const x = flowline(z) + rr(-EDGE + 2, EDGE - 2);
      // a serac is the block left standing BETWEEN two crevasses, so place them on
      // the lips rather than down in the slots
      const c = crevasseT(x, z);
      if (!onIce(x, z) || c < 0.16 || c > 0.52) continue;
      if (Math.abs(x - flowline(z)) < 9) continue;      // keep the rig's corridor clear
      // and it is a broken block, wider than it is tall as often as not, and it
      // leans: uniform uprights read as a row of gravestones
      const h = rr(1.3, 4.4), w = rr(1.2, 3.4) * (rnd() < 0.3 ? 1.6 : 1.0);
      p.set(x, Math.max(iceH(x, z), iceH(x, z + 1.5), iceH(x, z - 1.5)) + h * 0.26, z);
      e.set(rr(-0.42, 0.42), rr(0, Math.PI * 2), rr(-0.46, 0.46), 'YXZ');
      q.setFromEuler(e);
      s.set(w, h, w * rr(0.55, 1.2));
      this.seracs.setMatrixAt(n, m.compose(p, q, s));
      n++;
    }
    this.seracs.count = n;
    this.seracs.instanceMatrix.needsUpdate = true;
    ctx.scene.add(this.seracs);
  }
  update() { /* static geometry; all state response lives in the shared uniforms */ }
}

/* a leaning slab: a box tapered and sheared toward the top, built by hand so there
   is no dependency on BufferGeometryUtils being in the assembled bundle. */
function serac() {
  const g = new THREE.BoxGeometry(1, 1, 1, 1, 2, 1);
  g.translate(0, 0.5, 0);
  const pos = g.attributes.position;
  // jitter keyed to the CORNER, not the vertex index: a box duplicates its corners
  // once per face, and moving those copies independently tears the block open
  const j = (x, y, z, o) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7 + o) * 43758.5453; return (s - Math.floor(s)) - 0.5; };
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i), k = 1 - 0.42 * y;
    pos.setX(i, x * k + 0.22 * y * y + 0.22 * j(x, y, z, 1));
    pos.setY(i, y + 0.15 * j(x, y, z, 37));
    pos.setZ(i, z * (1 - 0.25 * y) + 0.20 * j(x, y, z, 71));
  }
  pos.needsUpdate = true;
  g.computeVertexNormals();
  return g;
}
