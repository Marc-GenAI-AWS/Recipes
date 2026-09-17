import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';

/* ═══ COMPONENT: Rain (effects) ═══
   Wind-sheared streaks wrapped around the moving camera so they always fill the
   view; gated by cur.rain (inert outside the storm). */
export class Rain {
  constructor(ctx) {
    const { scene, U, rnd, rr, renderer } = ctx;
    this.ctx = ctx;
    const N = 9000, p = new Float32Array(N * 3), s = new Float32Array(N);
    for (let i = 0; i < N; i++) { p[i * 3] = rr(-70, 70); p[i * 3 + 1] = rr(0, 60); p[i * 3 + 2] = rr(-95, 30); s[i] = rnd(); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('aSeed', new THREE.BufferAttribute(s, 1));
    this.mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, uniforms: uniformsFor(U, { uRain: F(0), uPx: F(renderer.getPixelRatio()) }),
      vertexShader: /* glsl */`attribute float aSeed; uniform float uTime, uRain, uWind, uPx; varying float vA;
      void main(){ vec3 p = position;
        float fall = mod(p.y - uTime * (34.0 + aSeed * 16.0), 60.0);
        p.y = fall; p.x += (60.0 - fall) * 0.18 * (0.4 + uWind);                       /* wind shear leans the streaks */
        /* keep the rain column wrapped around the moving camera so it always fills the view */
        p.x = mod(p.x - cameraPosition.x + 70.0, 140.0) - 70.0 + cameraPosition.x;
        p.z = mod(p.z - cameraPosition.z + 70.0, 140.0) - 70.0 + cameraPosition.z;
        vA = uRain * step(aSeed, uRain);
        vec4 mv = viewMatrix * vec4(p, 1.0);
        gl_PointSize = uPx * clamp(120.0 / max(-mv.z, 1.0), 3.0, 22.0) * (0.7 + 0.6 * aSeed);
        gl_Position = projectionMatrix * mv; }`,
      fragmentShader: /* glsl */`varying float vA;
      void main(){ vec2 c = gl_PointCoord - 0.5;
        float streak = smoothstep(0.5, 0.0, abs(c.x) * 7.0) * smoothstep(0.5, 0.05, abs(c.y));   /* tall thin dash */
        gl_FragColor = vec4(vec3(0.75, 0.80, 0.88), streak * vA * 0.45); }` });
    const pts = new THREE.Points(g, this.mat); pts.renderOrder = 7; pts.frustumCulled = false; scene.add(pts);
  }
  update() { this.mat.uniforms.uRain.value = this.ctx.cur.rain; }
}
