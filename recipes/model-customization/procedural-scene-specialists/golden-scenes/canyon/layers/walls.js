import * as THREE from 'three';
import { canyonH, HALF, LEN } from '../field.js';
import { rockMat } from '../materials.js';

/* ═══ COMPONENT: Walls (the ground) ═══
   One mesh carrying both the canyon floor and the walls that rise from it. Every
   vertex's y comes from canyonH(x, z) — the shared height field the scrub, the
   raptors' updraft and the camera all sample, so nothing floats or sinks. */
export class Walls {
  constructor(ctx) {
    this.ctx = ctx;
    const g = new THREE.PlaneGeometry(HALF * 2, LEN, 200, 340);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      pos.setY(i, canyonH(pos.getX(i), pos.getZ(i)));
    }
    pos.needsUpdate = true;
    g.computeVertexNormals();

    this.mesh = new THREE.Mesh(g, rockMat(ctx, [0.62, 0.34, 0.22], { grain: 1.0 }));
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);
  }
  update() { /* static geometry; all state response lives in the shared uniforms */ }
}
