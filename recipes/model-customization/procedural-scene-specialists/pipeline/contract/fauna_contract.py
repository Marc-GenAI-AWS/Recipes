"""Contract prompt for segment 6: the High Park Herd."""

FAUNA_PROMPT = """You are a senior Three.js creature-animation engineer. Write ONE layer of a modular,
single-file real-time scene ("High Park", a mountain-prairie basin under peaks): the HERD — a group
of large grazing animals in the home meadow. Output a single ES module that exports `class Herd`
and nothing else.

The module is assembled into a FROZEN host scene — you may only build the animals. Contract:

  export class Herd {
    constructor(ctx) {
      // ctx = { THREE, scene, camera, renderer, U, rnd, rr, cur }
      // Build 4-12 animals from THREE primitives (Capsule/Sphere/Cylinder/Cone/Box geometry) in
      // THREE.Group hierarchies (body, neck, head, legs with hip + knee pivots) and add them to ctx.scene.
    }
    update(dt, t) {
      // called every frame: move, turn and animate every animal.
    }
  }

PLACEMENT + MOTION (REQUIRED — the camera frames this meadow):
  - Animals live in the home meadow: keep each within 30 units of (12, -46) — steer back toward it
    when they stray. Real size: shoulder height ~1.4-2.0 units (these are LARGE animals).
  - Every frame set each group's position.y = groundH(x, z) so hooves stay on the terrain.
  - Face the direction of travel (rotation.y from heading); animate legs from a stride phase that
    advances with speed (swing hip + knee pivots); heads dip when grazing.
  - Read the host state every frame: ctx.cur.herdMood (0 calm .. 1 alarmed) and ctx.cur.herdSpeed
    (~0.3 .. 1.6). In the storm (herdMood > 0.7) the herd bunches and runs together; calm states
    graze and drift. The animals must visibly move or animate within any 4 seconds.
  - Use ONLY ctx.rnd() / ctx.rr(a, b) for randomness (seeded; never Math.random). No per-frame
    geometry or material creation — build everything in the constructor.

In scope (no import needed; importing is harmless — imports are stripped at assembly):
  - groundH(x, z)                  -> the frozen terrain height.
  - matterMat(ctx, [r, g, b], { mottle }) -> the scene's lit, fogged, cloud-shadowed material
    (colour components 0..1; mottle 0..1 = procedural hide variation). Use it for EVERY mesh so the
    animals sit in the scene's light; darker tints for hooves, manes, horns.
Rules: procedural only, no textures/assets/loaders; no lights, no DOM; <= ~110 lines; runs clean in
three.js r169. Keep total meshes <= 250.

BRIEF: {brief}

Output ONLY a single ```js fenced ES module. Nothing before or after the fence."""
