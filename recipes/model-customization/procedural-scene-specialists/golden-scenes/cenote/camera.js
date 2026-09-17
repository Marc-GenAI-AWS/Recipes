import * as THREE from 'three';

/* ═══ COMPONENT: Camera ═══
   Level camera: a slow orbit at mid-depth, looking horizontally at the pillar;
   surface along the top edge, mound at the bottom. Carries the diver's torch. */
export class CameraRig {
  constructor(ctx) {
    this.ctx = ctx;
    this.fwd = new THREE.Vector3(); this.e = new THREE.Euler(); this.look = new THREE.Vector3();
  }
  update(dt, t) {
    const { camera, U } = this.ctx;
    const a = 0.9 + t * 0.018 + 0.06 * Math.sin(t * 0.05), r = 15.5 + 1.0 * Math.sin(t * 0.031), y = -9.4 + 0.5 * Math.sin(t * 0.045) + 0.08 * Math.sin(t * 0.6);
    camera.position.set(Math.cos(a) * r, y, Math.sin(a) * r);
    this.look.set(0.5 * Math.sin(t * 0.03), y - 0.7 + 0.3 * Math.sin(t * 0.04), 0.5 * Math.cos(t * 0.035)); camera.lookAt(this.look);
    camera.getWorldDirection(this.fwd); this.e.set(0.22 * Math.sin(t * 0.37) - 0.1, 0.3 * Math.sin(t * 0.5), 0, 'YXZ'); this.fwd.applyEuler(this.e);
    U.uTorchPos.value.copy(camera.position).addScaledVector(this.fwd, 0.4); U.uTorchDir.value.copy(this.fwd);
  }
}
