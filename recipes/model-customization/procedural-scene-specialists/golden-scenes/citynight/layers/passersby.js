import * as THREE from 'three';
import { uniformsFor, F } from '../../contract/runtime.js';
import { G, VERT_WORLD, TAIL } from '../prelude.glsl.js';
import { streetH, onWalk, BLOCK, KERB_X, FACE_X } from '../field.js';

/* ═══ COMPONENT: Passersby (the fauna) ═══
   People on the pavement, and pigeons working the gutter. They are camera-facing
   quads — but a quad is a rectangle and a person is not, so the figure is carved
   out of it in the fragment shader with a signed-distance skeleton: head, torso,
   two legs that scissor on the walk phase, two arms that swing against them, and
   an umbrella on whoever thought to bring one. Untextured quads here read as
   cardboard; the discard is what makes them read as living figures.

   They are nearly black. All the shape they have comes from the neon and sodium
   catching a wet shoulder — which is the argument this whole world is making. */
export class Passersby {
  constructor(ctx) {
    this.ctx = ctx;
    const { rr, rnd } = ctx;
    const N = 34;

    this.folk = [];
    for (let i = 0; i < N; i++) {
      const pigeon = rnd() < 0.24;
      const side = rnd() < 0.5 ? -1 : 1;
      const dir = rnd() < 0.5 ? -1 : 1;
      // pigeons work the gutter; people keep to the pavement the field defines
      let x = pigeon ? side * rr(KERB_X - 0.8, KERB_X + 1.4) : side * rr(KERB_X + 1.0, FACE_X - 0.9);
      while (!pigeon && !onWalk(x, 0)) x = side * rr(KERB_X + 1.0, FACE_X - 0.9);
      this.folk.push({
        x, z: rr(-BLOCK / 2, BLOCK / 2), dir,
        h: pigeon ? rr(0.85, 1.05) : rr(1.58, 1.88),
        spd: pigeon ? rr(0.15, 0.5) : rr(0.9, 1.6) * dir,
        kind: pigeon ? 2 : (rnd() < 0.45 ? 1 : 0),
        seed: rnd(),
        coat: pigeon
          ? [0.10, 0.105, 0.12]
          : [0.035 + 0.05 * rnd(), 0.032 + 0.04 * rnd(), 0.040 + 0.055 * rnd()],
      });
    }

    const geo = figureQuad();
    this.mesh = new THREE.InstancedMesh(geo, figureMat(ctx), N);
    this.mesh.frustumCulled = false;
    const aFig = new Float32Array(N * 3), aCoat = new Float32Array(N * 3);
    this.folk.forEach((f, i) => {
      aFig[i * 3] = f.seed; aFig[i * 3 + 1] = Math.abs(f.spd); aFig[i * 3 + 2] = f.kind;
      aCoat.set(f.coat, i * 3);
    });
    geo.setAttribute('aFig', new THREE.InstancedBufferAttribute(aFig, 3));
    geo.setAttribute('aCoat', new THREE.InstancedBufferAttribute(aCoat, 3));
    ctx.scene.add(this.mesh);

    this.m = new THREE.Matrix4(); this.q = new THREE.Quaternion();
    this.p = new THREE.Vector3(); this.s = new THREE.Vector3();
    this.up = new THREE.Vector3(0, 1, 0);
  }

  update(dt, t) {
    const { m, q, p, s, up } = this;
    const cam = this.ctx.camera.position;
    for (let i = 0; i < this.folk.length; i++) {
      const f = this.folk[i];
      f.z += f.spd * dt * (f.kind === 2 ? 0.35 : 1);
      if (f.z > BLOCK / 2) f.z -= BLOCK; else if (f.z < -BLOCK / 2) f.z += BLOCK;
      // pigeons potter sideways; people hold their line on the pavement
      const x = f.kind === 2 ? f.x + 0.35 * Math.sin(t * 0.6 + f.seed * 6.28) : f.x;
      p.set(x, streetH(x, f.z) - 0.02, f.z);
      // billboard: yaw only, so the figure stays upright on its feet
      q.setFromAxisAngle(up, Math.atan2(cam.x - x, cam.z - f.z));
      s.set(f.h, f.h, f.h);
      this.mesh.setMatrixAt(i, m.compose(p, q, s));
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}

/* a quad 0.9 wide and 1.4 tall in units of body height: the extra headroom is for
   the umbrella, and the aspect is kept so the SDF below is in real proportions. */
function figureQuad() {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(
    [-0.45, 0, 0, 0.45, 0, 0, 0.45, 1.4, 0, -0.45, 1.4, 0], 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute([0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1], 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
  g.setIndex([0, 1, 2, 0, 2, 3]);
  return g;
}

const VERT_FIG = VERT_WORLD
  .replace('varying vec3 vP, vN;', 'varying vec3 vP, vN, vFig, vCoat; varying vec2 vUv; attribute vec3 aFig, aCoat;')
  .replace('vP = wp.xyz;', 'vP = wp.xyz; vFig = aFig; vCoat = aCoat; vUv = uv;');

const figureMat = (ctx) => new THREE.ShaderMaterial({
  side: THREE.DoubleSide,
  uniforms: uniformsFor(ctx.U, { uSway: F(0) }),
  vertexShader: VERT_FIG,
  fragmentShader: G + /* glsl */`
  varying vec3 vP, vN, vFig, vCoat; varying vec2 vUv;
  float limb(vec2 p, vec2 a, vec2 b){ vec2 pa = p - a, ba = b - a;
    return length(pa - ba * clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0)); }
  void main(){
    vec2 q = vec2((vUv.x - 0.5) * 0.9, vUv.y * 1.4);
    float ph = uTime * vFig.y * 3.4 + vFig.x * 6.283;
    float d = 1e3;
    if (vFig.z > 1.5) {                                    /* pigeon */
      float bob = 0.035 * sin(ph * 2.6);                   /* head-bob of a walking pigeon */
      d = min(d, length((q - vec2(0.0, 0.21 + bob * 0.3)) * vec2(1.0, 1.45)) - 0.155);
      d = min(d, length(q - vec2(0.13, 0.32 + bob)) - 0.058);
      d = min(d, limb(q, vec2(0.05, 0.30 + bob), vec2(0.13, 0.32 + bob)) - 0.035);
      d = min(d, limb(q, vec2(-0.12, 0.21), vec2(-0.31, 0.15)) - 0.032);
      d = min(d, limb(q, vec2(0.0, 0.06), vec2(0.02, 0.15)) - 0.013);
    } else {                                               /* a person, mid-stride */
      float sw = sin(ph), sc = cos(ph);
      vec2 hip = vec2(0.0, 0.47), sho = vec2(0.0, 0.80);
      d = min(d, limb(q, hip, hip + vec2(0.19 * sw, -0.47)) - 0.055);
      d = min(d, limb(q, hip, hip - vec2(0.19 * sw, 0.47)) - 0.055);
      d = min(d, limb(q, hip, sho) - 0.105 - 0.03 * sin(vFig.x * 9.0));
      d = min(d, limb(q, sho, sho + vec2(0.15 * sc, -0.30)) - 0.042);
      d = min(d, limb(q, sho, sho - vec2(0.15 * sc, 0.30)) - 0.042);
      d = min(d, length(q - vec2(0.0, 0.93)) - 0.087);
      if (vFig.z > 0.5) {                                  /* umbrella */
        float r = length(q - vec2(0.08, 1.02));
        d = min(d, max(abs(r - 0.33) - 0.022, 1.02 - q.y));
        d = min(d, limb(q, vec2(0.08, 1.02), vec2(0.08, 0.78)) - 0.013);
      }
    }
    if (d > 0.0) discard;

    /* fake a rounded body normal across the quad so a sign can rim one side */
    vec3 f = normalize(vN);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), f));
    vec3 n = normalize(f * 0.85 + right * (vUv.x - 0.5) * 2.4);
    vec3 lamps = neonGlow(vP, n);
    float rim = pow(abs(vUv.x - 0.5) * 2.0, 3.0);
    vec3 col = vCoat * (skyBounce(n) * 0.55 + lamps) + lamps * rim * (0.5 + 1.1 * uWetness);
    gl_FragColor = vec4(murk(col, vP), 1.0);
  ` + TAIL,
});
