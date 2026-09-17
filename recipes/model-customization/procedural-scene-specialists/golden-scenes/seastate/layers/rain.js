import * as THREE from 'three';

/* ═══ COMPONENT: Rain + lightning (effects/weather) ═══
   Rain as camera-wrapped line segments; owns the lightning scheduler and
   writes the shared uLightning channel (sky + ocean read it). Gated by cur.rain
   / cur.storminess so it is inert outside stormy states. */
export class Rain {
  constructor(ctx) {
    this.ctx = ctx;
    const COUNT = 1100;
    const AREA = 42;
    const HEIGHT = 26;

    const positions = new Float32Array(COUNT * 2 * 3);
    const ends = new Float32Array(COUNT * 2); // 0 = head, 1 = tail
    const seeds = new Float32Array(COUNT * 2);

    for (let i = 0; i < COUNT; i++) {
      const x = (ctx.rnd() - 0.5) * AREA;
      const y = ctx.rnd() * HEIGHT;
      const z = (ctx.rnd() - 0.5) * AREA - 6;
      const seed = ctx.rnd();
      for (let v = 0; v < 2; v++) {
        const idx = (i * 2 + v) * 3;
        positions[idx] = x;
        positions[idx + 1] = y;
        positions[idx + 2] = z;
        ends[i * 2 + v] = v;
        seeds[i * 2 + v] = seed;
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aEnd', new THREE.BufferAttribute(ends, 1));
    geo.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));

    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uRain: { value: 0 },
        uSlant: { value: 1.5 },
        uTint: { value: new THREE.Color(0.6, 0.68, 0.75) },
        uCamY: { value: 13 },
      },
      vertexShader: /* glsl */ `
        uniform float uTime;
        uniform float uSlant;
        uniform float uCamY;
        attribute float aEnd;
        attribute float aSeed;
        varying float vFade;

        void main() {
          vec3 p = position;
          float speed = 16.0 + aSeed * 9.0;
          float len = 0.55 + aSeed * 0.4;
          float h = 26.0;
          p.y = mod(p.y - uTime * speed, h) + uCamY - h * 0.55;
          // tail sits above the head, slanted by wind
          p.y += aEnd * len;
          p.x += aEnd * uSlant * 0.12 * len + (p.y - uCamY) * uSlant * 0.04;
          vFade = 1.0 - aEnd * 0.85;
          gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uRain;
        uniform vec3 uTint;
        varying float vFade;
        void main() {
          gl_FragColor = vec4(uTint, uRain * 0.22 * vFade);
        }
      `,
    });

    const mesh = new THREE.LineSegments(geo, mat);
    mesh.frustumCulled = false;
    mesh.renderOrder = 2;
    ctx.scene.add(mesh);
    this.mesh = mesh;
    this.mat = mat;
    this.nextStrike = 4;
    this.strikes = [];
    this._white = new THREE.Color(1, 1, 1);
  }
  lightningAt(t) {
    const cur = this.ctx.cur;
    if (cur.storminess > 0.5 && t > this.nextStrike) {
      this.strikes.push(t);
      this.nextStrike = t + 3 + this.ctx.rr(0, 8);
    }
    let v = 0;
    for (let i = this.strikes.length - 1; i >= 0; i--) {
      const age = t - this.strikes[i];
      if (age > 1.2) { this.strikes.splice(i, 1); continue; }
      v += Math.exp(-age * 9) * (0.65 + 0.35 * Math.sin(age * 85));
    }
    return Math.min(Math.max(v, 0), 1);
  }
  update(dt, t) {
    const ctx = this.ctx, cur = ctx.cur, cam = ctx.camera, ru = this.mat.uniforms;
    ctx.U.uLightning.value = this.lightningAt(t);
    ru.uTime.value = t;
    ru.uRain.value = cur.rain;
    ru.uSlant.value = 1.5 + cur.storminess * 5.0;
    ru.uTint.value.copy(cur.horizon).lerp(this._white, 0.4).multiplyScalar(0.6);
    ru.uCamY.value = cam.position.y;
    this.mesh.position.x = cam.position.x;
    this.mesh.position.z = cam.position.z;
    this.mesh.visible = cur.rain > 0.01;
  }
}
