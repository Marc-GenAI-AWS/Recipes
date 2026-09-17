import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { HOLE_R, HOLE_Y } from '../field.js';

/* ═══ COMPONENT: Skylight ═══
   The sky disc seen through the hole (sun glare / moon + stars), a glare halo,
   and the volumetric light pillar falling through the water (fake volume:
   brightness follows the view ray's path length through the cylinder). */
export class Skylight {
  constructor(ctx) {
    const { scene, U } = ctx;
    this.ctx = ctx;
    const sky = new THREE.Mesh(new THREE.CircleGeometry(HOLE_R * 1.08, 48), new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, {}), vertexShader: `varying vec2 vUv; varying vec3 vP; void main(){ vUv = uv; vP = (modelMatrix * vec4(position, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      uniform vec3 uSky; uniform float uSkyGlow, uMoon; uniform vec2 uSunOff; varying vec2 vUv; varying vec3 vP;
      void main(){ vec2 uv = vUv * 2.0 - 1.0; float r = length(uv);
        vec3 col = uSky * (1.05 - 0.4 * r * r) * (0.9 + 0.2 * fbm2(uv * 3.0 + uTime * 0.02));
        float sun = exp(-pow(length(uv - uSunOff) * 2.6, 2.0)); col += uSunC * sun * uSkyGlow * 1.6 + uSunC * uSkyGlow * 0.12 * exp(-r);
        vec2 st = floor(uv * 48.0); float s = step(0.975, hash1(vec3(st, 1.0))) * (0.6 + 0.4 * sin(uTime * 2.0 + hash1(vec3(st, 2.0)) * 20.0));
        float moon = smoothstep(0.075, 0.05, length(uv - vec2(0.35, -0.22)));
        col += uMoon * (vec3(0.85, 0.9, 1.0) * moon * 2.2 + vec3(0.9) * s * 0.9);
        col *= smoothstep(1.0, 0.9, r);
        gl_FragColor = vec4(fog(col, vP), 1.0);` + TAIL }));
    sky.rotation.x = Math.PI / 2; sky.position.y = HOLE_Y - 0.15; scene.add(sky);

    const glare = new THREE.Mesh(new THREE.CircleGeometry(HOLE_R * 1.9, 48), new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, {}), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `varying vec2 vUv; varying vec3 vP; void main(){ vUv = uv; vP = (modelMatrix * vec4(position, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + `uniform float uSkyGlow; varying vec2 vUv; varying vec3 vP;
      void main(){ float r = length(vUv * 2.0 - 1.0); float a = uSkyGlow * 0.22 * exp(-r * r * 4.0) * (0.85 + 0.15 * sin(uTime * 0.7));
        gl_FragColor = vec4(uSunC * a * fogAtt(vP), 1.0);` + TAIL }));
    glare.rotation.x = Math.PI / 2; glare.position.y = HOLE_Y - 0.4; scene.add(glare);

    const bg = new THREE.CylinderGeometry(HOLE_R, HOLE_R * 1.08, 21, 48, 1, true); bg.translate(0, -10.5, 0);
    /* fake volume: brightness follows the view ray's path length through the cylinder (its distance to the axis), not the fragment radius */
    this.beam = new THREE.Mesh(bg, new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, { uHalo: U.uHalo, uInv: { value: new THREE.Matrix4() } }), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide,
      vertexShader: `varying vec3 vL, vP, vC; uniform mat4 uInv; void main(){ vL = position; vP = (modelMatrix * vec4(position, 1.0)).xyz; vC = (uInv * vec4(cameraPosition, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vL, vP, vC; uniform float uHalo;
      void main(){ vec3 d = normalize(vL - vC); vec3 nrm = cross(d, vec3(0.0, 1.0, 0.0)); float ln = max(length(nrm), 1e-4);
        float b = dot(vC, nrm) / ln;                                            /* signed distance of the view ray from the beam axis */
        float path = pow(sqrt(max(0.0, 1.0 - b * b / (uBeamR * uBeamR))), 2.4), y = vL.y;
        float streak = 0.25 + 0.75 * fbm2(vec2(b * 0.8 + 3.0, y * 0.05 - uTime * 0.14));
        streak *= 0.55 + 0.45 * fbm2(vec2(b * 2.2 - 7.0, y * 0.25 + uTime * 0.04));
        float depth = exp(y * 0.032) * smoothstep(-21.0, -17.0, y);
        float hal = mix(1.0, 0.45, smoothstep(uHaloY + 1.0, uHaloY - 1.0, vP.y)) * (1.0 + 0.9 * uHalo * exp(-abs(vP.y - uHaloY) * 1.5));
        float a = uBeamI * path * streak * depth * hal * 0.5 * fogAtt(vP);
        gl_FragColor = vec4(uSunC * (0.85 + 0.35 * streak), a);` + TAIL }));
    this.beam.renderOrder = 5; scene.add(this.beam);
  }
  update() { const cur = this.ctx.cur; this.beam.rotation.z = cur.tilt; this.beam.updateMatrixWorld(); this.beam.material.uniforms.uInv.value.copy(this.beam.matrixWorld).invert(); }
}
