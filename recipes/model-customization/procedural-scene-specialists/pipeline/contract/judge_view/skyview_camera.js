import * as THREE from 'three';
import { groundH } from '../../highpark/field.js';

/* Judge-only camera: the normal knoll viewpoint, pitched ~35° up toward the saddle so the peaks
   sit along the bottom edge and the sky fills the frame. Used to judge sky brief adherence —
   in the scene camera's framing the sky is a thin band behind mist and horizon haze. */
export class CameraRig {
  constructor(ctx) { this.ctx = ctx; this.look = new THREE.Vector3(); }
  update(dt, t) {
    const camera = this.ctx.camera;
    const x = 16 + Math.sin(t * 0.021) * 2.0, z = 20;
    camera.position.set(x, groundH(x, z) + 4.0, z);
    // 180 units out toward the saddle, ~125 up: the ridge tops land near the bottom of the frame
    this.look.set(4 + Math.sin(t * 0.045) * 6, groundH(4, -160) + 150, -160);
    camera.lookAt(this.look);
  }
}
