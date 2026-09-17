import * as THREE from 'three';
import { matterMat } from '../materials.js';
import { groundH } from '../field.js';

/* ═══ COMPONENT: Herd (fauna) ═══
   Wild horses (barrel, neck, head+ears, mane ridge, tail, two-joint legs) with
   graze / drift / trot behaviours; they bunch and run in the storm, settle at
   dusk. Reads groundH + cur.herdMood/herdSpeed. */
const HIDE = [[0.45, 0.32, 0.22], [0.28, 0.20, 0.15], [0.62, 0.55, 0.48], [0.20, 0.16, 0.14], [0.55, 0.38, 0.24]];
export class Herd {
  constructor(ctx) {
    this.ctx = ctx;
    this.horses = [];
    for (let i = 0; i < 7; i++) this.horses.push(this.makeHorse(HIDE[i % HIDE.length], i === 0 ? 1.12 : ctx.rr(0.9, 1.05), i));
  }
  makeHorse(tint, s, i) {
    const ctx = this.ctx, { scene, rnd } = ctx;
    const g = new THREE.Group();
    const hide = matterMat(ctx, tint, { mottle: 0.25 }), dark = matterMat(ctx, [tint[0] * 0.45, tint[1] * 0.45, tint[2] * 0.45], { mottle: 0.15 });
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.44, 1.15, 6, 12), hide); body.rotation.z = Math.PI / 2; body.position.y = 1.45; body.scale.set(1, 1, 0.82); g.add(body);
    const chest = new THREE.Mesh(new THREE.SphereGeometry(0.42, 10, 8), hide); chest.position.set(0.62, 1.42, 0); chest.scale.set(0.9, 1, 0.82); g.add(chest);
    const rump = new THREE.Mesh(new THREE.SphereGeometry(0.44, 10, 8), hide); rump.position.set(-0.62, 1.5, 0); rump.scale.set(0.95, 1, 0.85); g.add(rump);
    const neckP = new THREE.Group(); neckP.position.set(0.85, 1.72, 0); g.add(neckP);
    const neck = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.72, 4, 8), hide); neck.position.set(0.24, 0.34, 0); neck.rotation.z = -0.72; neckP.add(neck);
    const headP = new THREE.Group(); headP.position.set(0.52, 0.66, 0); neckP.add(headP);
    const head = new THREE.Mesh(new THREE.CapsuleGeometry(0.13, 0.42, 4, 8), hide); head.rotation.z = Math.PI / 2 - 0.45; head.position.set(0.2, -0.05, 0); headP.add(head);
    const muzzle = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.115, 0.22, 8), dark); muzzle.rotation.z = Math.PI / 2 - 0.45; muzzle.position.set(0.42, -0.16, 0); headP.add(muzzle);
    for (const sd of [-1, 1]) { const ear = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.17, 5), hide); ear.position.set(-0.02, 0.16, sd * 0.09); ear.rotation.x = sd * 0.25; headP.add(ear); }
    /* mane: a ridge of flattened boxes along the neck top */
    for (let k = 0; k < 5; k++) { const mm = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.22 - k * 0.02, 0.05), dark); mm.position.set(0.05 + k * 0.13, 0.30 + k * 0.13, 0); mm.rotation.z = -0.7; neckP.add(mm); }
    const tail = new THREE.Mesh(new THREE.CapsuleGeometry(0.07, 0.75, 3, 6), dark); tail.position.set(-1.05, 1.35, 0); tail.rotation.z = 0.45; g.add(tail);
    const legs = [];
    const mkLeg = (x, z) => { const hip = new THREE.Group(); hip.position.set(x, 1.25, z);
      const up = new THREE.Mesh(new THREE.CapsuleGeometry(0.10, 0.55, 3, 6), hide); up.position.y = -0.3; hip.add(up);
      const knee = new THREE.Group(); knee.position.y = -0.6;
      const lo = new THREE.Mesh(new THREE.CapsuleGeometry(0.065, 0.55, 3, 6), hide); lo.position.y = -0.3; knee.add(lo);
      const hoof = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.065, 0.1, 6), dark); hoof.position.y = -0.62; knee.add(hoof);
      hip.add(knee); g.add(hip); legs.push({ hip, knee }); };
    mkLeg(0.62, 0.22); mkLeg(0.62, -0.22); mkLeg(-0.62, 0.22); mkLeg(-0.62, -0.22);
    g.scale.setScalar(s); scene.add(g);
    const a0 = rnd() * 6.283;
    return { g, neckP, headP, tail, legs, x: 12 + Math.cos(a0) * ctx.rr(4, 16), z: -46 + Math.sin(a0) * ctx.rr(4, 14),
             heading: rnd() * 6.283, speed: 0, mode: 'graze', timer: ctx.rr(1, 5), ph: rnd() * 6.283, s };
  }
  update(dt, t) {
    const ctx = this.ctx, cur = ctx.cur, rnd = ctx.rnd, rr = ctx.rr, mood = cur.herdMood, spd = cur.herdSpeed;
    for (const h of this.horses) {
      h.timer -= dt;
      if (h.timer <= 0) {
        const r = rnd();
        if (mood > 0.7) { h.mode = r < 0.75 ? 'run' : 'alert'; h.heading = -1.1 + rr(-0.35, 0.35); }       /* storm: run east together */
        else h.mode = r < 0.5 ? 'graze' : r < 0.8 ? 'drift' : 'alert';
        if (h.mode === 'drift') h.heading += rr(-1.2, 1.2);
        h.timer = rr(2, 6) * (1.3 - mood * 0.8);
      }
      const want = h.mode === 'run' ? 5.2 : h.mode === 'drift' ? 1.1 : 0;
      h.speed += (want * spd - h.speed) * dt * 2.2;
      h.x += Math.cos(h.heading) * h.speed * dt; h.z += -Math.sin(h.heading) * h.speed * dt;
      const dx = h.x - 12, dz = h.z + 46;                                                 /* keep to the home meadow */
      if (dx * dx + dz * dz > 30 * 30) h.heading = Math.atan2(dz, -dx) + rr(-0.3, 0.3);
      h.g.position.set(h.x, groundH(h.x, h.z), h.z); h.g.rotation.y = h.heading;
      /* gait: walk = diagonal pairs; run = gallop-ish bound with body pitch */
      const run = THREE.MathUtils.clamp(h.speed / 4, 0, 1);
      const stride = t * (4.5 + 5.5 * run) * (0.25 + Math.min(1, h.speed)) + h.ph;
      h.legs.forEach((l, i) => {
        const phase = stride + (run > 0.5 ? (i < 2 ? 0 : Math.PI * 0.8) : (i === 0 || i === 3 ? 0 : Math.PI));
        const amp = Math.min(1, h.speed) * (0.45 + 0.35 * run);
        l.hip.rotation.z = Math.sin(phase) * amp;
        l.knee.rotation.z = Math.max(0, -Math.cos(phase)) * (0.7 + 0.5 * run) * Math.min(1, h.speed);
      });
      h.g.position.y += Math.abs(Math.sin(stride * (run > 0.5 ? 0.5 : 1))) * 0.09 * run * h.s;
      h.g.rotation.z = Math.sin(stride * 0.5) * 0.05 * run;
      const neckWant = h.mode === 'graze' ? 0.95 : h.mode === 'alert' ? -0.30 : 0.1 + run * 0.25;
      h.neckP.rotation.z += (neckWant - h.neckP.rotation.z) * dt * 3;
      h.headP.rotation.y = h.mode === 'alert' ? Math.sin(t * 0.7 + h.ph) * 0.5 : 0;
      h.headP.rotation.z = h.mode === 'graze' ? 0.35 + Math.sin(t * 1.4 + h.ph) * 0.08 : Math.sin(stride) * 0.05 * run;
      h.tail.rotation.z = 0.45 + Math.sin(t * (1.5 + 3 * cur.wind) + h.ph) * (0.12 + 0.25 * cur.wind) + run * 0.5;
    }
  }
}
