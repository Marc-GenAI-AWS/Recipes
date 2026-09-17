import * as THREE from 'three';
import { matterMat } from '../materials.js';
import { groundH, fbmJ, BASIN_R } from '../field.js';

/* ═══ COMPONENT: Outcrops ═══
   Lichen-mottled granite boulders half-sunk in the turf; one big split erratic
   near camera. Reads groundH for placement. */
export class Outcrops {
  constructor(ctx) {
    const { scene, rnd, rr } = ctx;
    const g = new THREE.IcosahedronGeometry(1, 2), p = g.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); v.multiplyScalar(1 + (fbmJ(v.x * 2 + 4, v.y * 2 + v.z, 3) - 0.5) * 0.34); p.setXYZ(i, v.x, v.y, v.z); }
    g.computeVertexNormals();
    const rocks = new THREE.InstancedMesh(g, matterMat(ctx, [0.55, 0.51, 0.45], { mottle: 1 }), 26), d = new THREE.Object3D();
    for (let i = 0; i < 26; i++) {
      const big = i < 2; const x = big ? rr(-30, -14) : rr(-BASIN_R * 0.7, BASIN_R * 0.7), z = big ? rr(-18, -4) : rr(-170, 20);
      const s = big ? rr(2.4, 3.6) : rr(0.5, 1.8);
      d.position.set(x, groundH(x, z) + s * 0.25, z); d.rotation.set(rnd() * 3, rnd() * 3, rnd() * 3);
      d.scale.set(s, s * rr(0.55, 0.8), s * rr(0.7, 1.2)); d.updateMatrix(); rocks.setMatrixAt(i, d.matrix);
    }
    scene.add(rocks);
  }
}
