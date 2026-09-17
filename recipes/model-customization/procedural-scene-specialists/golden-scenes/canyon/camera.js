import * as THREE from 'three';
import { canyonH, meander, LEN } from './field.js';

/* ═══ COMPONENT: Camera ═══
   A walk down the canyon floor: the rig tracks the corridor's meander so the walls
   stay on both sides, holds a little above the height field, and looks slightly up
   so the bright ribbon of sky stays in frame. That ribbon is what makes the depth
   read, so every state is judged from a viewpoint that includes it. */
export class CameraRig {
  constructor(ctx) {
    this.ctx = ctx;
    this.look = new THREE.Vector3();
  }
  update(dt, t) {
    const { camera } = this.ctx;
    // drift down the corridor and wrap, so the walk never leaves the built geometry
    const z = ((t * 3.4 + LEN / 2) % LEN) - LEN / 2;
    const x = meander(z) + 1.6 * Math.sin(t * 0.14);
    const ground = canyonH(x, z);
    camera.position.set(x, ground + 1.9 + 0.12 * Math.sin(t * 1.3), z);

    const zf = z - 14;
    this.look.set(
      meander(zf) + 1.2 * Math.sin(t * 0.09),
      canyonH(meander(zf), zf) + 5.2 + 2.4 * Math.sin(t * 0.07),
      zf,
    );
    camera.lookAt(this.look);
    // Roll about the camera's OWN forward axis. Assigning camera.rotation.z after a
    // lookAt is not equivalent: for some headings the Euler decomposition lands on the
    // (x≈-π, z≈π) branch, and overwriting z alone flips the up vector, rendering the
    // world upside down — which passes every structural gate. This rig's heading happens
    // to avoid that branch, but the idiom is correct only by luck, so don't copy it.
    camera.rotateZ(0.02 * Math.sin(t * 0.11));
  }
}
