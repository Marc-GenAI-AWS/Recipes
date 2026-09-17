import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';

/* ═══ COMPONENT: AirLife ═══
   A hawk circling the saddle thermal (big slow circles) and swallows low over
   the grass. Point sprites drawn as little winged dashes. */
export class AirLife {
  constructor(ctx) {
    const { scene, U, rnd, rr, renderer } = ctx;
    this.ctx = ctx;
    const mk = (n, size) => {
      const g = new THREE.BufferGeometry(), p = new Float32Array(n * 3), s = new Float32Array(n);
      for (let i = 0; i < n; i++) { p.set([rr(-80, 80), rr(6, 30), rr(-120, 10)], i * 3); s[i] = rnd(); }
      g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('aSeed', new THREE.BufferAttribute(s, 1));
      const mat = new THREE.ShaderMaterial({ transparent: true, depthWrite: false,
        uniforms: uniformsFor(U, { uVis: F(1), uPx: F(renderer.getPixelRatio()), uSize: F(size) }),
        vertexShader: `attribute float aSeed; uniform float uTime, uPx, uVis, uSize; varying float vA, vFlap;
        void main(){ vec3 p = position; float t = uTime * (0.5 + aSeed * 0.5) * ${size > 600 ? '0.22' : '1.0'};
          p.x += sin(t + aSeed * 6.0) * ${size > 600 ? '38.0' : '26.0'}; p.z += cos(t * 1.2 + aSeed * 4.0) * ${size > 600 ? '26.0' : '18.0'};
          p.y += sin(t * 2.2 + aSeed) * 2.5;
          vFlap = sin(uTime * (${size > 600 ? '1.4' : '11.0'} + aSeed * 4.0)); vA = uVis * step(aSeed, uVis);
          vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_PointSize = uPx * uSize / max(-mv.z, 1.0); gl_Position = projectionMatrix * mv; }`,
        fragmentShader: `varying float vA, vFlap; void main(){ vec2 c = gl_PointCoord - 0.5;
          float wy = 0.15 * vFlap * (1.0 - abs(c.x) * 2.2);
          float a = smoothstep(0.05, 0.0, abs(c.y - wy) - 0.013) * step(abs(c.x), 0.44);
          gl_FragColor = vec4(vec3(0.10, 0.09, 0.10), a * vA); }` });
      const pts = new THREE.Points(g, mat); scene.add(pts); return mat;
    };
    this.swallows = mk(10, 420);
    this.hawkMat = mk(1, 1500);                       /* one hawk, big slow circles, near-fixed wings */
  }
  update() { const cur = this.ctx.cur; this.swallows.uniforms.uVis.value = Math.min(cur.hawk * 1.4, 1); this.hawkMat.uniforms.uVis.value = cur.hawk > 0.15 ? 1 : 0; }
}
