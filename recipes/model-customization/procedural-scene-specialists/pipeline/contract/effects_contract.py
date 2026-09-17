"""Contract prompt for segment 5 (effects): the High Park dawn Mist.

Rain was the first choice but is invisible to the verifier (light streaks on a bright
sky: rain forced on ≈ rain removed, calib_presence.py 2026-09-14); mist is the state-gated
atmospheric effect the camera clearly sees (p98 tile diff 37.5 at dawn)."""

EFFECTS_PROMPT = """You are a senior Three.js graphics engineer. Write ONE layer of a modular,
single-file real-time scene ("High Park", a mountain-prairie basin under peaks): the MIST — low
translucent ground mist lying in the prairie hollows at dawn. Output a single ES module that exports
`class Mist` and nothing else.

The module is assembled into a FROZEN host scene — you may only build the mist. Contract:

  export class Mist {
    constructor(ctx) {
      // ctx = { THREE, scene, camera, renderer, U, rnd, rr, cur }
      // Build the mist from a few transparent meshes (planes / billboards / slabs) and add them to ctx.scene.
    }
    // update(dt, t) is optional — the host already animates uTime and uMist every frame.
  }

VISIBILITY (REQUIRED — the verifier checks it):
  - The host drives `uMist` (in U): 1.0 at first-light, 0.0 in cloud-shadows, 0.15 in storm-break,
    0.3 at gold-dusk. Multiply your alpha by uMist: the mist must be CLEARLY visible across the
    basin in front of the camera at first-light, and invisible when uMist is 0.
  - Place it where the camera sees it: lying just above the terrain (y = groundH(x, z) + 1..6) over
    roughly x in [-110, 150], z in [-190, -20]; wide and low (e.g. planes ~150-250 wide, 5-20 tall).
  - Material: ShaderMaterial, transparent: true, depthWrite: false, uniforms = uniformsFor(ctx.U, {});
    set renderOrder = 2 on each mesh. One shared material is fine.

In scope (no import needed; importing is harmless — imports are stripped at assembly):
  - groundH(x, z), uniformsFor(U, extra). Use ctx.rnd() / ctx.rr(a, b) for placement (seeded; never Math.random).
  - G     -> GLSL prelude; PREPEND it to your fragmentShader. It declares uTime, uSkyTop,
             uSkyHorizon, uSunC, uSunI, uSunDir, uFogC, uFogD, uWind, uCloud, uShadowAmt, uShaft,
             uFlash, uShaftDir, uSaddle and provides hash1(vec3), noise3(vec3), fbm3(vec3),
             fbm2(vec2), windAt(vec2 xz, float t), cloudShad(vec3 p), shaftMask(vec3 p),
             fog(vec3 color, vec3 p), fogAtt(vec3 p), and the constant FLASH_C (vec3).
  - TAIL  -> APPEND to your fragmentShader; it closes main() with tonemapping + colorspace.
NOT in G — declare yourself: `uniform float uMist;` and your varyings. The vertex shader is your
own (G is NOT prepended there): pass uv and the world position (modelMatrix * vec4(position, 1.0)).
CRITICAL: do NOT re-declare any uniform G declares (a duplicate is a GLSL "redefinition" error).

Look: soft-edged drifting bands — alpha from fbm2 noise advected slowly with uTime (and uWind),
faded to 0 at every edge of each mesh so no hard rectangle shows; colour from uFogC lifted by uSunI,
plus uSunC * shaftMask(vP) where the light corridor crosses it; finish with
`gl_FragColor = vec4(fog(col, vP), alpha);` followed by TAIL.
Rules: procedural only; <= 8 meshes; <= ~50 lines; no loops in the fragment shader; runs clean in
three.js r169.

BRIEF: {brief}

Output ONLY a single ```js fenced ES module. Nothing before or after the fence."""
