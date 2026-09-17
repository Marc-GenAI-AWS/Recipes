import * as THREE from 'three';
import { F } from '../../contract/runtime.js';
import { VERT_WORLD, FRAG_ROCK } from '../prelude.glsl.js';
import { rockMat } from '../materials.js';
import { floorH, fbmJ, DOME, DOME_C, HOLE_ANGLE } from '../field.js';

/* ═══ COMPONENT: Cavern ═══
   Displaced limestone dome with a circular skylight cut out of the ceiling,
   hanging stalactites, and a silt seabed with rubble and fallen slabs. Owns
   the floor field (floorH) that Reef/Fish/Bubbles sample. */
export class Cavern {
  constructor(ctx) {
    const { scene, rnd, rr } = ctx;
    const g = new THREE.IcosahedronGeometry(1, 6), pos = g.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      const rim = 1 - THREE.MathUtils.smoothstep(v.y, 0.88, 0.961);                 /* keep the skylight rim clean */
      const d = (fbmJ(v.x * 3.2, v.y * 3.2, v.z * 3.2) - 0.45) * 0.1 + (fbmJ(v.x * 9, v.y * 9, v.z * 9, 3) - 0.5) * 0.035
              + 0.025 * Math.sin(Math.atan2(v.z, v.x) * 22 + v.y * 4) * (1 - v.y * v.y);   /* vertical fluting */
      v.multiplyScalar(1 + d * rim); pos.setXYZ(i, v.x * DOME.x, v.y * DOME.y + DOME_C, v.z * DOME.z);
    }
    g.computeVertexNormals();
    const nrm = g.attributes.normal; for (let i = 0; i < nrm.count; i++) nrm.setXYZ(i, -nrm.getX(i), -nrm.getY(i), -nrm.getZ(i));
    const domeMat = rockMat(ctx, [0.42, 0.38, 0.32], { side: THREE.BackSide, mottle: 0.9 });
    domeMat.vertexShader = VERT_WORLD.replace('vP = wp.xyz;', 'vP = wp.xyz; vL = position;').replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vL;');
    domeMat.fragmentShader = FRAG_ROCK.replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vL; uniform vec3 uDome; uniform float uDomeC, uHoleCos;')
      .replace('vec3 n = normalize(vN), p = vP;', 'vec3 n = normalize(vN), p = vP; vec3 ls = (vL - vec3(0.0, uDomeC, 0.0)) / uDome; if (normalize(ls).y > uHoleCos) discard;');
    Object.assign(domeMat.uniforms, { uDome: { value: DOME }, uDomeC: F(DOME_C), uHoleCos: F(Math.cos(HOLE_ANGLE)) });
    scene.add(new THREE.Mesh(g, domeMat));

    const fg = new THREE.PlaneGeometry(70, 70, 180, 180); fg.rotateX(-Math.PI / 2);
    const fp = fg.attributes.position; for (let i = 0; i < fp.count; i++) fp.setY(i, floorH(fp.getX(i), fp.getZ(i)));
    fg.computeVertexNormals();
    scene.add(new THREE.Mesh(fg, rockMat(ctx, [0.38, 0.34, 0.28], { mottle: 0.8 })));

    const rubble = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(1, 0), rockMat(ctx, [0.3, 0.27, 0.23]), 45), d = new THREE.Object3D();
    for (let i = 0; i < 45; i++) {
      const a = rnd() * 6.283, r = 2 + Math.pow(rnd(), 0.8) * 19, s = rr(0.2, 0.8); const x = Math.cos(a) * r, z = Math.sin(a) * r;
      d.position.set(x, floorH(x, z) + s * 0.35, z); d.rotation.set(rnd() * 3, rnd() * 3, rnd() * 3); d.scale.set(s, s * rr(0.5, 0.9), s * rr(0.7, 1.2));
      d.updateMatrix(); rubble.setMatrixAt(i, d.matrix);
    }
    scene.add(rubble);
    const slabs = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(1, 1), rockMat(ctx, [0.4, 0.36, 0.31], { mottle: 0.8 }), 9);
    for (let i = 0; i < 9; i++) {
      const a = i / 9 * 6.283 + rr(-0.3, 0.3), r = rr(14, 21), sx = rr(2.2, 4.5); const x = Math.cos(a) * r, z = Math.sin(a) * r;
      d.position.set(x, floorH(x, z) + sx * 0.3, z); d.rotation.set(rr(-0.4, 0.4), rnd() * 3, rr(-0.4, 0.4)); d.scale.set(sx, sx * rr(0.45, 0.8), sx * rr(0.7, 1.3));
      d.updateMatrix(); slabs.setMatrixAt(i, d.matrix);
    }
    scene.add(slabs);

    const cg = new THREE.ConeGeometry(1, 1, 7); cg.rotateX(Math.PI); cg.translate(0, -0.5, 0);
    const stal = new THREE.InstancedMesh(cg, rockMat(ctx, [0.58, 0.53, 0.45], { mottle: 0.5 }), 60), down = new THREE.Vector3(0, -1, 0), q = new THREE.Quaternion();
    for (let i = 0; i < 60; i++) {
      const th = rr(HOLE_ANGLE * 1.25, 0.85), ph = rnd() * 6.283, sy = Math.cos(th), sr = Math.sin(th);
      const p = new THREE.Vector3(Math.cos(ph) * sr * DOME.x, sy * DOME.y + DOME_C, Math.sin(ph) * sr * DOME.z).multiplyScalar(0.985);
      const inward = new THREE.Vector3(-Math.cos(ph) * sr, -sy * 0.55, -Math.sin(ph) * sr).normalize();
      q.setFromUnitVectors(down, inward); const s = rr(0.22, 0.6);
      d.position.copy(p); d.quaternion.copy(q); d.scale.set(s, rr(1.4, 4.2), s); d.updateMatrix(); stal.setMatrixAt(i, d.matrix);
    }
    scene.add(stal);

    /* dripstone columns hanging from the ceiling down through the water, and stalagmites on the floor rim */
    const drip = rockMat(ctx, [0.46, 0.42, 0.35], { mottle: 0.9 });
    for (let i = 0; i < 8; i++) {
      const th = rr(0.6, 1.0), ph = i / 8 * 6.283 + rr(-0.25, 0.25), sr = Math.sin(th);
      const x = Math.cos(ph) * sr * DOME.x * 0.93, z = Math.sin(ph) * sr * DOME.z * 0.93, top = Math.cos(th) * DOME.y + DOME_C + 1.5, end = rr(-13, -3);
      const R = rr(0.7, 1.7), pts = [];
      for (let k = 0; k <= 22; k++) { const f = k / 22; pts.push(new THREE.Vector2(Math.max(0.02, R * Math.pow(1 - f, 0.65) * (1 + 0.16 * Math.sin(f * 38 + i)) * (1 + 0.1 * Math.sin(f * 9))), top - (top - end) * f)); }
      const m = new THREE.Mesh(new THREE.LatheGeometry(pts.reverse(), 14), drip); m.position.set(x, 0, z); m.rotation.y = rnd() * 6.283; scene.add(m);
    }
    for (let i = 0; i < 7; i++) {
      const ph = i / 7 * 6.283 + rr(-0.3, 0.3), r = rr(11, 19), x = Math.cos(ph) * r, z = Math.sin(ph) * r, h = rr(2.5, 7), R = h * rr(0.16, 0.26), pts = [];
      for (let k = 0; k <= 14; k++) { const f = k / 14; pts.push(new THREE.Vector2(Math.max(0.02, R * Math.pow(1 - f, 0.55) * (1 + 0.12 * Math.sin(f * 25 + i))), floorH(x, z) - 0.5 + h * f)); }
      const m = new THREE.Mesh(new THREE.LatheGeometry(pts, 12), drip); m.position.set(x, 0, z); scene.add(m);
    }
  }
}
