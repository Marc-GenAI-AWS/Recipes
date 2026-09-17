import * as THREE from 'three';
import { iceH, flowline, BASIN } from './field.js';

/* ═══ COMPONENT: Camera ═══
   A traverse UP the glacier: the rig walks the ice a little left of the medial
   moraine so the rubble stripe runs away to the right, holds head height above the
   shared field, and looks up-basin at the headwall with a shallow lift.

   The lift is the whole framing decision. Point it further down and the frame is
   nothing but snow, which in this world means an unreadable white sheet; point it
   up and you lose the crevasses that give the surface its scale. A little under ten
   degrees keeps the ice in the bottom half, the headwall across the middle, and a
   band of that near-black zenith along the top — which is what makes the snow read
   as blinding rather than merely pale. */
export class CameraRig {
  constructor(ctx) {
    this.ctx = ctx;
    this.look = new THREE.Vector3();
  }
  update(dt, t) {
    const { camera } = this.ctx;
    // walk up-glacier and wrap, so the traverse never leaves the built basin
    const span = 200;
    const z = 104 - ((t * 2.6) % span);
    const x = flowline(z) - 1.5 + 5.0 * Math.sin(t * 0.06);
    // ride the lip, not the slot: take the highest of three samples so a crevasse
    // passing under the rig does not drop the whole frame nine metres
    const g = Math.max(iceH(x, z), iceH(x, z + 2.4), iceH(x, z - 2.4), iceH(x + 2.0, z));
    camera.position.set(x, g + 1.85 + 0.10 * Math.sin(t * 1.1), z);

    const zf = z - 36;
    const xf = flowline(zf) + 2.5 * Math.sin(t * 0.045);
    this.look.set(xf, iceH(xf, zf) + 3.5 + 1.2 * Math.sin(t * 0.08), zf);
    camera.lookAt(this.look);
    camera.rotation.z = 0.018 * Math.sin(t * 0.09);
  }
}

export const TRAVERSE = BASIN;   // the rig stays inside the basin the field defines
