import * as THREE from 'three';
import { crustH, BOWL } from './field.js';

/* ═══ COMPONENT: Camera ═══
   A slow traverse of the caldera floor, on a drifting arc so the seam network
   passes under and across the view instead of running away to a vanishing point.

   The framing rule for this world is the opposite of the usual one. The bright
   thing is DOWN, so the rig sits low — a little over three units over the crust —
   and holds a shallow downward tilt: enough that the fissures fill the lower half
   and light the frame, but not so much that the caldera wall and the ash vault
   leave it. Lose the wall and the world has no scale; lose the floor and it has no
   light. Every state is judged from a viewpoint that keeps both. */
export class CameraRig {
  constructor(ctx) {
    this.ctx = ctx;
    this.look = new THREE.Vector3();
  }
  update(dt, t) {
    const { camera } = this.ctx;
    const a = t * 0.030;
    const r = 40 + 13 * Math.sin(t * 0.019 + 1.1);
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    const ground = crustH(x, z);
    camera.position.set(x, ground + 6.2 + 0.20 * Math.sin(t * 1.15), z);

    // aim ahead along the arc and a touch inboard, so the pan and the far wall
    // both stay in shot; the shallow rise and fall re-weights floor against sky
    const af = a + 0.60;
    const rf = Math.min(BOWL - 8, r + 10 * Math.sin(t * 0.045));
    const fx = Math.cos(af) * rf, fz = Math.sin(af) * rf;
    this.look.set(fx, crustH(fx, fz) - 0.4 + 1.5 * Math.sin(t * 0.055), fz);
    camera.lookAt(this.look);
    // roll about the camera's OWN forward axis. Assigning camera.rotation.z after a
    // lookAt is not the same thing: for these headings the Euler decomposition lands
    // on the (x≈-π, z≈π) branch, and overwriting z alone rolls the rig 180° — the
    // caldera renders upside down, floor on the ceiling, and still passes every gate.
    camera.rotateZ(0.018 * Math.sin(t * 0.09));
  }
}
