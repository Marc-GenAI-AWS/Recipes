import * as THREE from 'three';
import { groundH } from './field.js';

/* ═══ COMPONENT: Camera ═══
   Slow arc along the knoll south of the meadow, breathing height, always
   framing herd → basin → saddle in thirds. */
export class CameraRig {
  constructor(ctx) { this.ctx = ctx; this.look = new THREE.Vector3(); }
  update(dt, t) {
    const camera = this.ctx.camera;
    /* slow arc along the knoll south of the meadow, always framing herd → basin → saddle */
    const a = t * 0.021, x = 16 + Math.sin(a) * 10, z = 20 + Math.cos(a * 0.7) * 5;
    camera.position.set(x, groundH(x, z) + 4.0 + Math.sin(t * 0.09) * 0.35, z);
    /* thirds: grass foreground, herd + basin, then ridge + saddle + sky */
    this.look.set(4 + Math.sin(t * 0.045) * 8, groundH(4, -160) + 24 + Math.sin(t * 0.06) * 1.5, -160);
    camera.lookAt(this.look);
  }
}
