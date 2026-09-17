import * as THREE from 'three';

/* ═══════════════════════════════════════════════════════════════════════
   SCENE CONTRACT — shared runtime (v1)
   The scene-agnostic engine every scene boots against. See SCENE_CONTRACT.md.
   Provides: uniform helpers, a seeded RNG, a state machine (enumerated OR
   factored manifest), and the assembler loop. A scene supplies a `sceneDef`
   (uniforms, layer classes, camera, state resolver, per-frame apply) to boot().
   ═══════════════════════════════════════════════════════════════════════ */

/* uniform helpers — a ShaderMaterial's uniforms is uniformsFor({...locals}) */
export const F  = (v) => ({ value: v });
export const C3 = () => ({ value: new THREE.Color() });
export const V3 = (x = 0, y = 0, z = 0) => ({ value: new THREE.Vector3(x, y, z) });
export const uniformsFor = (U, extra = {}) => ({ ...U, ...extra });

/* deterministic RNG (park–miller); no Math.random in scene code */
export function makeRNG(seed = 7) {
  let s = (seed >>> 0) || 1;
  const rnd = () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; };
  const rr = (a, b) => a + (b - a) * rnd();
  return { rnd, rr };
}

/* cur → target exponential interpolation of every visual parameter.
   `resolve(name)` returns a fresh target object (numbers, THREE.Color, THREE.Vector3).
   Colors/Vectors lerp via .lerp; numbers lerp arithmetically. */
export class StateMachine {
  constructor({ initial, resolve, rate = 1.2, onApply }) {
    this.resolve = resolve; this.rate = rate; this.onApply = onApply;
    this.cur = {}; this.target = {};
    this.setState(initial, true);
  }
  setState(name, instant = false) {
    const t = this.resolve(name);
    for (const k in t) if (!(k in this.cur)) { const v = t[k]; this.cur[k] = (v && v.clone) ? v.clone() : v; }
    this.target = t;
    if (instant) for (const k in t) { const v = t[k]; this.cur[k] = (v && v.clone) ? v.clone() : v; }
  }
  tick(dt, t, ctx) {
    const k = 1 - Math.exp(-dt * this.rate), cur = this.cur, tg = this.target;
    for (const key in tg) {
      const c = cur[key], target = tg[key];
      if (typeof c === 'number') cur[key] = c + (target - c) * k;
      else if (c && c.lerp) c.lerp(target, k);
    }
    if (this.onApply) this.onApply(cur, ctx, t);
  }
}

/* boot the frozen skeleton: renderer, scene, camera, layers[], main loop.
   sceneDef: { meta, buildUniforms(), resolveState(name), initialState(),
               applyToUniforms(cur,ctx,t), layers:[Class], camera:Class,
               postfx?:Class, setupUI?(ctx,sm), onHashChange?(sm) } */
export function boot(canvas, sceneDef) {
  const meta = sceneDef.meta || {};
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, meta.pixelRatio ?? 2));
  renderer.setSize(innerWidth, innerHeight);
  if (meta.toneMapping && THREE[meta.toneMapping]) renderer.toneMapping = THREE[meta.toneMapping];

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(meta.fov ?? 55, innerWidth / innerHeight, meta.near ?? 0.5, meta.far ?? 10000);
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const { rnd, rr } = makeRNG(meta.seed ?? 7);
  const U = sceneDef.buildUniforms();
  const ctx = { THREE, renderer, scene, camera, U, rnd, rr, reducedMotion, cur: null };

  const sm = new StateMachine({
    initial: sceneDef.initialState(),
    resolve: (name) => sceneDef.resolveState(name),
    rate: meta.rate ?? 1.2,
    onApply: (cur, c, t) => sceneDef.applyToUniforms(cur, c, t),
  });
  ctx.cur = sm.cur;

  // scene-level setup (background, renderer tweaks) before layers are built
  if (sceneDef.setup) sceneDef.setup(ctx);

  const layers = (sceneDef.layers || []).map((L) => new L(ctx));
  const rig = sceneDef.camera ? new sceneDef.camera(ctx) : null;
  const post = sceneDef.postfx ? new sceneDef.postfx(ctx) : null;

  addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight); if (post && post.resize) post.resize(innerWidth, innerHeight);
  });
  addEventListener('hashchange', () => sceneDef.onHashChange ? sceneDef.onHashChange(sm) : sm.setState(location.hash.slice(1)));
  if (sceneDef.setupUI) sceneDef.setupUI(ctx, sm);

  const clock = new THREE.Clock(); let t = 0;
  function frame() {
    const dt = Math.min(clock.getDelta(), 0.05); t += dt;
    U.uTime.value = t;
    sm.tick(dt, t, ctx);
    if (rig) rig.update(dt, t, ctx);
    for (const l of layers) if (l.update) l.update(dt, t);
    if (post) post.render(); else renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  frame();
  return { ctx, sm, layers, rig, post };
}
