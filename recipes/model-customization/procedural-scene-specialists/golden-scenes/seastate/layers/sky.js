import * as THREE from 'three';
import { atmosphereUniformsGLSL, atmosphereGLSL } from '../prelude.glsl.js';

/* ═══ COMPONENT: Sky ═══
   The sky dome. Owns the cloud-deck drift; reads the shared palette (U) that
   applyToUniforms publishes. skyRadiance() is shared with the ocean so the
   water mirrors the exact sky above it. */
export class Sky {
  constructor(ctx) {
    this.ctx = ctx;
    const geo = new THREE.SphereGeometry(4200, 64, 32);
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      defines: { CLOUD_OCT: 5, SKY_FULL: 1 },
      uniforms: ctx.U,
      vertexShader: /* glsl */ `
        varying vec3 vWorldPos;
        void main() {
          vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader:
        atmosphereUniformsGLSL +
        atmosphereGLSL +
        /* glsl */ `
        varying vec3 vWorldPos;
        void main() {
          vec3 dir = normalize(vWorldPos - cameraPosition);
          vec3 col = skyRadiance(dir);
          col = acesTonemap(col * uExposure);
          col = pow(col, vec3(0.4545));
          col += (hash21(gl_FragCoord.xy) - 0.5) / 255.0; // dither: kills gradient banding
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.frustumCulled = false;
    ctx.scene.add(mesh);
  }
  update(dt) {
    const cur = this.ctx.cur, off = this.ctx.U.uCloudOff.value;
    off.x += 0.62 * cur.cloudDrift * dt * 60;
    off.y += 0.35 * cur.cloudDrift * dt * 60;
  }
}
