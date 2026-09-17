import * as THREE from 'three';
import { uniformsFor } from '../../contract/runtime.js';
import { G, TAIL, VERT_WORLD } from '../prelude.glsl.js';
import { groundH } from '../field.js';

/* ═══ COMPONENT: Prairie (ground) ═══
   Rolling turf heightfield built from the shared groundH; soil patches, cloud
   shadows and the shaft corridor read on the ground. */
export class Prairie {
  constructor(ctx) {
    const { scene, U } = ctx;
    const geo = new THREE.PlaneGeometry(1000, 780, 190, 150); geo.rotateX(-Math.PI / 2); geo.translate(0, 0, -160);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) pos.setY(i, groundH(pos.getX(i), pos.getZ(i)));
    geo.computeVertexNormals();
    scene.add(new THREE.Mesh(geo, new THREE.ShaderMaterial({
      uniforms: uniformsFor(U, {}), vertexShader: VERT_WORLD, fragmentShader: G + /* glsl */`
      varying vec3 vP, vN; uniform vec3 uGrassA, uGrassB;
      void main(){ vec3 p = vP, n = normalize(vN);
        float turf = fbm2(p.xz * 0.05) * 0.5 + 0.5, soil = smoothstep(0.72, 0.85, fbm2(p.xz * 0.03 + 9.0));
        vec3 base = mix(uGrassA * 1.1, uGrassB * 0.55, turf); base = mix(base, vec3(0.30, 0.24, 0.16), soil * 0.6);
        base *= 0.92 + 0.16 * noise3(p * 2.0);
        float lam = max(dot(n, normalize(uSunDir)), 0.0);
        vec3 light = mix(uSkyHorizon, uSkyTop, 0.5) * (0.30 + 0.2 * n.y)
                   + uSunC * uSunI * lam * (0.35 + 0.6 * cloudShad(p)) + uSunC * shaftMask(p) * 1.3 + FLASH_C * uFlash * (0.5 + 0.4 * n.y);
        gl_FragColor = vec4(fog(base * light, p), 1.0);` + TAIL })));
  }
}
