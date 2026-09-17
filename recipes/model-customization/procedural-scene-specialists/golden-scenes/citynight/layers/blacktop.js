import * as THREE from 'three';
import { streetH, BLOCK, FACE_X } from '../field.js';
import { tarmacMat, brickMat } from '../materials.js';

/* ═══ COMPONENT: Blacktop (the ground) ═══
   The street surface and the walls that stand on it. Every vertex's y comes from
   streetH(x, z) — the shared field the weeds, the pedestrians and the camera all
   sample — so the kerb is one kerb and nothing floats or sinks.

   This layer carries the world's signature. The carriageway is not a grey plane:
   it is a cambered surface with water standing in its low camber, and through
   wetSpec() it mirrors every sign and lamp in the scene back at the camera. The
   frontages are the second half of the lighting model — a stacked grid of lit
   windows above the street. */
export class Blacktop {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr, rnd } = ctx;

    // ── the road, the kerbs and both pavements, as one height-field mesh ──
    const g = new THREE.PlaneGeometry(32, BLOCK, 190, 320);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) pos.setY(i, streetH(pos.getX(i), pos.getZ(i)));
    pos.needsUpdate = true;
    g.computeVertexNormals();
    this.road = new THREE.Mesh(g, tarmacMat(ctx, { aggr: 1.0 }));
    this.road.frustumCulled = false;
    ctx.scene.add(this.road);

    // ── the frontages: instanced blocks packed along both pavements ──
    const blocks = [];
    for (let side = -1; side <= 1; side += 2) {
      let z = -BLOCK / 2;
      while (z < BLOCK / 2) {
        const w = rr(7, 19), d = rr(7, 13), h = rr(9, 24);
        blocks.push({ x: side * (FACE_X + d / 2 + rr(0, 0.5)), y: h / 2, z: z + w / 2, w, d, h,
          seed: rnd(), lit: rr(0.35, 0.95), off: rr(0, 3.1) });
        z += w + rr(0.2, 0.8);
      }
    }
    const geo = new THREE.BoxGeometry(1, 1, 1);
    this.faces = new THREE.InstancedMesh(geo, brickMat(ctx, [0.115, 0.105, 0.115]), blocks.length);
    this.faces.frustumCulled = false;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3();
    const aFace = new Float32Array(blocks.length * 3);
    blocks.forEach((b, i) => {
      p.set(b.x, b.y, b.z); s.set(b.d, b.h, b.w);
      this.faces.setMatrixAt(i, m.compose(p, q, s));
      aFace[i * 3] = b.seed; aFace[i * 3 + 1] = b.lit; aFace[i * 3 + 2] = b.off;
    });
    this.faces.instanceMatrix.needsUpdate = true;
    geo.setAttribute('aFace', new THREE.InstancedBufferAttribute(aFace, 3));
    ctx.scene.add(this.faces);
  }
  update() { /* static geometry; every state response lives in the shared uniforms */ }
}
