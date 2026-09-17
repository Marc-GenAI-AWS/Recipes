import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { coralMat } from '../materials.js';
import { floorH, fbmJ } from '../field.js';

/* ═══ COMPONENT: Reef ═══
   Coral across the seabed: staghorn branches, boulder/brain heads, table
   corals, swaying sea fans, tube sponges. Saturation follows the light,
   fluorescence under the torch. Reads groundH (floorH) for placement. */
export class Reef {
  constructor(ctx) {
    const { scene, U, rnd, rr } = ctx;
    const d = new THREE.Object3D(), pick = arr => arr[Math.floor(rnd() * arr.length)];
    const spot = () => { const r = 2.5 + 19 * Math.pow(rnd(), 1.5), a = rnd() * 6.283; return [Math.cos(a) * r, Math.sin(a) * r]; };
    const inst = (geom, n, fill) => { const cols = new Float32Array(n * 3); geom.setAttribute('aCol', new THREE.InstancedBufferAttribute(cols, 3));
      const m = new THREE.InstancedMesh(geom, coralMat(ctx), n); for (let i = 0; i < n; i++) { const c = fill(i); d.updateMatrix(); m.setMatrixAt(i, d.matrix); cols.set(c, i * 3); } scene.add(m); return m; };
    /* staghorn: colonies of tilted tapered branches */
    const SH = [[0.9, 0.55, 0.35], [0.75, 0.35, 0.55], [0.85, 0.78, 0.45], [0.55, 0.7, 0.55]]; let col = null, cx = 0, cz = 0;
    inst(new THREE.ConeGeometry(0.14, 1, 6).translate(0, 0.5, 0), 260, i => {
      if (i % 10 === 0) { [cx, cz] = spot(); col = pick(SH); }
      const a = rnd() * 6.283, tilt = rr(0.25, 0.85), h = rr(1.0, 2.6), x = cx + rr(-0.5, 0.5), z = cz + rr(-0.5, 0.5);
      d.position.set(x, floorH(x, z) - 0.1, z); d.rotation.set(tilt * Math.cos(a), 0, tilt * Math.sin(a)); d.scale.set(h * 0.9, h, h * 0.9); return col; });
    /* boulder and brain heads: noise-displaced spheres */
    const bg = new THREE.IcosahedronGeometry(1, 4), bp = bg.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < bp.count; i++) { v.fromBufferAttribute(bp, i); v.multiplyScalar(1 + (fbmJ(v.x * 3, v.y * 3, v.z * 3, 3) - 0.5) * 0.2 + (fbmJ(v.x * 9, v.y * 9, v.z * 9, 2) - 0.5) * 0.06); bp.setXYZ(i, v.x, v.y, v.z); } bg.computeVertexNormals();
    const BH = [[0.8, 0.6, 0.3], [0.5, 0.62, 0.35], [0.75, 0.45, 0.5], [0.65, 0.55, 0.25]];
    inst(bg, 38, () => { const [x, z] = spot(), sc = rr(0.4, 1.6); d.position.set(x, floorH(x, z) + sc * 0.25, z); d.rotation.set(0, rnd() * 6.283, 0); d.scale.set(sc, sc * rr(0.55, 0.85), sc); return pick(BH); });
    /* table corals: a flat plate on a stalk (two instances each) */
    const TB = [[0.6, 0.45, 0.25], [0.5, 0.48, 0.3]];
    inst(new THREE.CylinderGeometry(1, 0.7, 1, 12), 28, i => { if (i % 2 === 0) { [cx, cz] = spot(); col = pick(TB); }
      const w = 1.4 + (i % 7) * 0.3, h = 0.9 + (i % 5) * 0.25, y0 = floorH(cx, cz);
      if (i % 2 === 0) { d.position.set(cx, y0 + h, cz); d.scale.set(w, 0.09, w * rr(0.75, 1.0)); } else { d.position.set(cx, y0 + h * 0.5, cz); d.scale.set(0.22, h, 0.22); }
      d.rotation.set(0, rnd() * 6.283, 0); return col; });
    /* tube sponges: clusters of cylinders */
    const SP = [[0.55, 0.3, 0.72], [0.9, 0.8, 0.32], [0.85, 0.45, 0.3]];
    inst(new THREE.CylinderGeometry(0.14, 0.2, 1, 8).translate(0, 0.5, 0), 90, i => { if (i % 5 === 0) { [cx, cz] = spot(); col = pick(SP); }
      const x = cx + rr(-0.45, 0.45), z = cz + rr(-0.45, 0.45), h = rr(0.6, 1.8); d.position.set(x, floorH(x, z) - 0.05, z); d.rotation.set(rr(-0.25, 0.25), 0, rr(-0.25, 0.25)); d.scale.set(1, h, 1); return col; });
    /* sea fans: lattice planes that sway */
    const FN = [[0.6, 0.2, 0.45], [0.9, 0.35, 0.25], [0.85, 0.6, 0.2]];
    const fanMat = new THREE.ShaderMaterial({ uniforms: uniformsFor(U, { uSat: U.uSat, uGlow: U.uGlow }), side: THREE.DoubleSide,
      vertexShader: /* glsl */`
      attribute vec3 aCol; varying vec3 vP, vN, vCol; varying vec2 vUv; uniform float uTime;
      void main(){ mat4 m = modelMatrix * instanceMatrix; vec4 wp = m * vec4(position, 1.0);
        wp.xz += uv.y * uv.y * 0.35 * vec2(sin(uTime * 0.7 + wp.x * 0.8), cos(uTime * 0.6 + wp.z * 0.7));
        vP = wp.xyz; vN = normalize(mat3(m) * normal); vCol = aCol; vUv = uv; gl_Position = projectionMatrix * viewMatrix * wp; }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP, vN, vCol; varying vec2 vUv; uniform float uSat, uGlow;
      void main(){ vec2 q = vUv - vec2(0.5, 0.0); float fan = smoothstep(0.5, 0.42, length(q * vec2(1.0, 1.1))) * step(0.0, vUv.y);
        float net = max(abs(sin(vUv.x * 70.0 + sin(vUv.y * 9.0))), abs(sin(vUv.y * 46.0 + q.x * 12.0))); float edge = fbm2(vUv * 9.0);
        float a = fan * step(0.55, net) * step(0.32, edge + 0.25 * vUv.y); if (a < 0.5) discard;
        vec3 n = normalize(vN), p = vP; float bm = beamMask(p); vec3 base = mix(vec3(dot(vCol, vec3(0.33))), vCol, uSat);
        vec3 light = uAmbC * uAmbI * 0.9 + uSunC * uSunI * (0.15 + 0.6 * bm) * (0.5 + 0.5 * abs(dot(n, -uSunDir))) + torch(p, n) + torch(p, -n);
        gl_FragColor = vec4(fog(base * light + vCol * torchAt(p) * uGlow * 1.3, p), 1.0);` + TAIL });
    const fans = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).translate(0, 0.5, 0), fanMat, 34), fc = new Float32Array(34 * 3);
    fans.geometry.setAttribute('aCol', new THREE.InstancedBufferAttribute(fc, 3));
    for (let i = 0; i < 34; i++) { const [x, z] = spot(), sc = rr(1.0, 2.6); d.position.set(x, floorH(x, z) - 0.1, z); d.rotation.set(0, rnd() * 6.283, rr(-0.15, 0.15)); d.scale.set(sc, sc * rr(0.7, 1.0), 1);
      d.updateMatrix(); fans.setMatrixAt(i, d.matrix); fc.set(pick(FN), i * 3); }
    scene.add(fans);
  }
}
