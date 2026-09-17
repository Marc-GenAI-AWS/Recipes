import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL } from '../prelude.glsl.js';
import { groundH, BASIN_R } from '../field.js';

/* ═══ COMPONENT: Grass (vegetation) ═══
   ~42k instanced blades bent by the shared wind field; tips backlit and
   blazing inside the shaft corridor. Reads groundH for placement. */
export class Grass {
  constructor(ctx) {
    const { scene, U, rnd, rr } = ctx;
    const N = 42000;
    const blade = new THREE.PlaneGeometry(0.10, 1, 1, 3); blade.translate(0, 0.5, 0);
    { const p = blade.attributes.position; for (let i = 0; i < p.count; i++) p.setX(i, p.getX(i) * (1 - p.getY(i) * 0.85)); }
    const seeds = new Float32Array(N);
    const mesh = new THREE.InstancedMesh(blade, new THREE.ShaderMaterial({
      side: THREE.DoubleSide, uniforms: uniformsFor(U, {}),
      vertexShader: G + /* glsl */`
      attribute float aSeed; varying vec3 vP; varying float vH, vSeed;
      void main(){ vSeed = aSeed; vec3 p = position; vH = p.y;
        mat4 m = modelMatrix * instanceMatrix;
        vec4 base = m * vec4(0.0, 0.0, 0.0, 1.0);
        float w = windAt(base.xz, uTime) + 0.10 * sin(uTime * 2.6 + aSeed * 40.0) * uWind;
        vec4 wp = m * vec4(p, 1.0);
        float bend = w * p.y * p.y;
        wp.x += bend * 1.1; wp.z += bend * 0.3; wp.y -= bend * bend * 0.4;
        vP = wp.xyz; gl_Position = projectionMatrix * viewMatrix * wp; }`,
      fragmentShader: G + /* glsl */`
      varying vec3 vP; varying float vH, vSeed; uniform vec3 uGrassA, uGrassB;
      void main(){
        vec3 col = mix(uGrassA, uGrassB, vH * vH * (0.6 + 0.6 * fract(vSeed * 7.3)));
        float cs = cloudShad(vP), sm = shaftMask(vP);
        col *= 0.35 + 0.75 * uSunI * cs;
        col += uSunC * pow(vH, 5.0) * (0.2 * uSunI * cs + 1.4 * sm);
        col += uSunC * sm * 0.5 * (0.4 + 0.6 * vH);                    /* backlit tips, blazing inside the shaft */
        col += mix(uSkyHorizon, uSkyTop, 0.5) * 0.03;
        col += FLASH_C * uFlash * (0.6 + 0.7 * vH);
        gl_FragColor = vec4(fog(col, vP), 1.0);` + TAIL }), N);
    const d = new THREE.Object3D();
    for (let i = 0; i < N; i++) {
      const near = i < N * 0.6;
      const x = near ? rr(-70, 70) : rr(-BASIN_R, BASIN_R), z = near ? rr(-95, 30) : rr(-250, 40);
      d.position.set(x, groundH(x, z) - 0.04, z);
      d.rotation.set(0, rnd() * 6.283, (rnd() - 0.5) * 0.22);
      const h = rr(0.6, 1.5) * (near ? 1 : 1.7); d.scale.set(near ? 1 : 1.8, h, 1);
      d.updateMatrix(); mesh.setMatrixAt(i, d.matrix); seeds[i] = rnd();
    }
    blade.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seeds, 1));
    scene.add(mesh);
  }
}
