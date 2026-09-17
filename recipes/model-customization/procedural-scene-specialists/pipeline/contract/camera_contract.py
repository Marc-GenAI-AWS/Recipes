"""Contract prompt for segment 3: the High Park CameraRig."""

CAMERA_PROMPT = """You are a senior Three.js cinematographer-engineer. Write ONE layer of a modular,
single-file real-time scene ("High Park", a mountain-prairie basin under peaks): the CAMERA RIG.
Output a single ES module that exports `class CameraRig` and nothing else.

The module is assembled into a FROZEN host scene — you may only move the camera. Contract:

  export class CameraRig {
    constructor(ctx) {
      // ctx = { THREE, scene, camera, renderer, U, rnd, rr, cur }
      // ctx.camera is a PerspectiveCamera (fov 48, near 0.1, far 1600) the host renders with.
    }
    update(dt, t) {
      // called every frame; t = seconds since start. Set ctx.camera.position and aim it
      // (camera.lookAt(x, y, z)). Do nothing else.
    }
  }

In scope (no import needed; importing is harmless — imports are stripped at assembly):
  - groundH(x, z)  -> the frozen terrain height at a world position.
  - SADDLE         -> THREE.Vector3(0, 38, -340): the gap in the peaks where the hero light falls.
  - BASIN_R        -> 200: the prairie's rough radius around the origin.

Scene layout (world units, +y up): the prairie floor rolls around y≈0; the herd grazes near
(12, groundH, -46); the peaks rise north of z≈-250 (up to ~y=300 at z≈-500); the saddle is at
SADDLE. The host looks best framed from the south looking north (toward -z): grass and herd low
in frame, the basin and ridge line across the middle, sky on top.

HARD RULES (a violation fails the verifier):
  - Every frame the camera must be ABOVE the terrain: position.y >= groundH(position.x, position.z) + 1.5.
  - Stay inside the basin: -150 <= x <= 150 and -150 <= z <= 60.
  - Keep sky above and ground below in frame (don't point at the sky or straight down).
  - Motion must be smooth and continuous in t (no jumps, no randomness per frame — use sin/cos of t).
  - The shot must visibly MOVE: over any 4 seconds the camera travels at least ~1.5 units or its
    aim swings noticeably, even for a "slow" pace (a static frame fails the animation check).
    The verifier samples t ≈ 2-6 s, so motion must be visible FROM THE START — no ease-in from rest
    (e.g. never drive the move with 0.5 - 0.5*cos(w*t), which is flat near t = 0).
  - Do not create controls, DOM, lights or objects; do not touch ctx.scene or U. <= ~50 lines.
  - Runs clean in three.js r169.

Four host states (first-light, cloud-shadows, storm-break, gold-dusk) switch the lighting and
weather; your shot may stay the same across them (reading ctx.cur is optional).

BRIEF: {brief}

Output ONLY a single ```js fenced ES module. Nothing before or after the fence."""
