import * as THREE from 'three';
import { streetH, BLOCK } from './field.js';

/* ═══ COMPONENT: Camera ═══
   A walk down the carriageway, not the pavement: from the crown of the road both
   frontages stand on either side and — the point of this world — the wet surface
   in front of you carries the reflection of every sign above it. The rig therefore
   holds eye height, aims 18 m down the street and tips slightly DOWN, so the lower
   half of every frame is reflective road. Aim it at the sky and this scene stops
   being about its own lighting. Wraps at the ends of the block. */
export class CameraRig {
  constructor(ctx) { this.ctx = ctx; this.look = new THREE.Vector3(); }
  update(dt, t) {
    const { camera } = this.ctx;
    const z = ((-t * 2.6 + BLOCK * 1.5) % BLOCK) - BLOCK / 2;   // walking toward -z
    const x = -2.3 + 0.7 * Math.sin(t * 0.19);
    camera.position.set(x, streetH(x, z) + 1.64 + 0.035 * Math.sin(t * 2.4), z);

    const zf = z - 18;
    this.look.set(
      x * 0.4 + 1.1 * Math.sin(t * 0.13),
      streetH(0, zf) + 1.30 + 0.45 * Math.sin(t * 0.08),
      zf,
    );
    camera.lookAt(this.look);
    camera.rotation.z = 0.013 * Math.sin(t * 0.17);
  }
}
