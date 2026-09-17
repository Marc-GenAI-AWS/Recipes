import * as THREE from 'three';
import { crustH, SPAN, BOWL } from '../field.js';
import { crustMat } from '../materials.js';

/* ═══ COMPONENT: Crust (the ground) ═══
   The caldera floor and the wall that rises out of it, in one mesh. Every vertex's
   y comes from crustH(x, z) — the shared height field the scrub, the vents and the
   camera all sample, so nothing floats or sinks.

   This is the layer that carries the world's signature. The fissures are modelled
   twice over: as GEOMETRY (crustH digs a trench along every seam, so the crust has
   a lip that catches its own light) and as EMISSION (crackGlow paints the molten
   floor of the trench). Remove this layer and the scene has no light source at all,
   which is the point — everything else in the caldera is lit by what happens here.

   The tessellation is deliberately fine: at 240x240 the seam trenches are 3-4 quads
   wide, which is the minimum that keeps them reading as cut channels rather than as
   a glowing decal painted on a flat plate. */
export class Crust {
  constructor(ctx) {
    this.ctx = ctx;
    const g = new THREE.PlaneGeometry(SPAN, SPAN, 240, 240);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) pos.setY(i, crustH(pos.getX(i), pos.getZ(i)));
    pos.needsUpdate = true;
    g.computeVertexNormals();

    this.mesh = new THREE.Mesh(g, crustMat(ctx, [0.21, 0.170, 0.155], { rough: 1.0 }));
    this.mesh.frustumCulled = false;
    ctx.scene.add(this.mesh);

    // a handful of spatter cones straddling the hottest seams: low, steep, and lit
    // hard on their inward faces, which is what makes the floor read as a floor.
    const cones = coneField(ctx);
    if (cones) {
      this.cones = new THREE.Mesh(cones, crustMat(ctx, [0.18, 0.135, 0.125], { rough: 0.8 }));
      this.cones.frustumCulled = false;
      ctx.scene.add(this.cones);
    }
  }
  update() { /* static geometry; all state response lives in the shared uniforms */ }
}

/* merged cone geometry, built by hand — BufferGeometryUtils may not be in the
   assembled bundle, so nothing here may depend on it. */
function coneField(ctx) {
  const { rr } = ctx;
  const pos = [], idx = [];
  const SEG = 9, N = 26;
  for (let c = 0; c < N; c++) {
    const a = rr(0, Math.PI * 2), r = rr(30, BOWL - 14);
    const cx = Math.cos(a) * r, cz = Math.sin(a) * r;
    const base = crustH(cx, cz), rad = rr(2.4, 6.0), hgt = rr(1.4, 3.8);
    const o = pos.length / 3;
    pos.push(cx, base + hgt, cz);                                  // apex
    for (let s = 0; s < SEG; s++) {
      const t = (s / SEG) * Math.PI * 2, wob = 0.75 + 0.5 * Math.sin(t * 3 + a);
      const bx = cx + Math.cos(t) * rad * wob, bz = cz + Math.sin(t) * rad * wob;
      pos.push(bx, crustH(bx, bz) - 0.3, bz);
    }
    for (let s = 0; s < SEG; s++) idx.push(o, o + 1 + ((s + 1) % SEG), o + 1 + s);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}
