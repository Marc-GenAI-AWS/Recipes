/* ═══ COMPONENT: Camera ═══
   A near-static bow view: the camera holds at deck height, breathing with a
   gentle swell that scales with the sea state, plus subtle mouse parallax. */
export class CameraRig {
  constructor(ctx) {
    this.ctx = ctx;
    this.CAM_HEIGHT = 13;
    this.BASE_PITCH = -0.15; // slightly downward, horizon in the upper third
    this.lookX = 0; this.lookY = 0;
    this.smoothX = 0; this.smoothY = 0;

    const cam = ctx.camera;
    cam.position.set(0, this.CAM_HEIGHT, 0);
    cam.rotation.order = 'YXZ';
    cam.rotation.x = this.BASE_PITCH;

    if (!ctx.reducedMotion) {
      addEventListener('pointermove', (ev) => {
        this.lookX = (ev.clientX / innerWidth - 0.5) * 2;
        this.lookY = (ev.clientY / innerHeight - 0.5) * 2;
      });
    }
  }
  update(dt, t) {
    if (this.ctx.reducedMotion) return;
    const cam = this.ctx.camera, cur = this.ctx.cur;
    cam.position.y = this.CAM_HEIGHT + Math.sin(t * 0.35) * 0.35 * (0.5 + cur.ampMul);
    this.smoothX += (this.lookX - this.smoothX) * (1 - Math.exp(-dt * 3));
    this.smoothY += (this.lookY - this.smoothY) * (1 - Math.exp(-dt * 3));
    cam.rotation.y = -this.smoothX * 0.045;
    cam.rotation.x = this.BASE_PITCH - this.smoothY * 0.03 + Math.sin(t * 0.22) * 0.004;
  }
}
