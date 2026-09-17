"""Contract prompt for segment 4: the High Park Grass field."""

VEGETATION_PROMPT = """You are a senior Three.js graphics engineer. Write ONE layer of a modular,
single-file real-time scene ("High Park", a mountain-prairie basin under peaks): the GRASS — an
instanced field of grass blades covering the prairie. Output a single ES module that exports
`class Grass` and nothing else.

The module is assembled into a FROZEN host scene — you may only build the grass. Contract:

  export class Grass {
    constructor(ctx) {
      // ctx = { THREE, scene, camera, renderer, U, rnd, rr, cur }
      // Build exactly ONE THREE.InstancedMesh and add it to ctx.scene.
    }
  }

PLACEMENT (REQUIRED — the herd, rocks and camera share this ground):
  - At most 45000 instances. Use ONLY ctx.rnd() / ctx.rr(a, b) for randomness (seeded; never Math.random).
  - Put ~60% of blades in the near meadow: x in [-70, 70], z in [-95, 30]; the rest across
    x in [-BASIN_R, BASIN_R], z in [-250, 40].
  - Each blade sits ON the frozen terrain: instance position y = groundH(x, z) - 0.04.
    Random yaw and height; blade geometry is a thin tapered strip with its base at y = 0.

In scope (no import needed; importing is harmless — imports are stripped at assembly):
  - groundH(x, z), BASIN_R (200), uniformsFor(U, extra).
  - G     -> GLSL prelude; PREPEND it to BOTH your vertexShader and fragmentShader. It declares
             uTime, uSkyTop, uSkyHorizon, uSunC, uSunI, uSunDir, uFogC, uFogD, uWind, uCloud,
             uShadowAmt, uShaft, uFlash, uShaftDir, uSaddle and provides hash1(vec3), noise3(vec3),
             fbm3(vec3), fbm2(vec2), `float windAt(vec2 xz, float t)` (returns a SCALAR wind strength,
             NOT a vector — `vec2 w = windAt(...)` is a GLSL compile error), cloudShad(vec3 p), shaftMask(vec3 p),
             fog(vec3 color, vec3 p), fogAtt(vec3 p), and the constant FLASH_C (vec3).
  - TAIL  -> APPEND to your fragmentShader; it closes main() with tonemapping + colorspace.
NOT in G — declare yourself: `uniform vec3 uGrassA, uGrassB;` (the state's root/tip grass colours)
and any attributes you add (e.g. a per-instance seed via THREE.InstancedBufferAttribute).
CRITICAL: do NOT re-declare any uniform G declares (a duplicate is a GLSL "redefinition" error).

Shaders: ShaderMaterial, side: THREE.DoubleSide, uniforms = uniformsFor(ctx.U, {}).
  - Vertex: `mat4 m = modelMatrix * instanceMatrix;` get the blade's world base; take
    `float w = windAt(base.xz, uTime);` (a scalar) and bend the tip ALONG A DIRECTION YOU CHOOSE, as a
    3-component vector so it adds straight onto the world position:
    `vec3 dir = normalize(vec3(1.0, 0.0, 0.3)); wp.xyz += dir * bend;` — never add a vec2 to a vec3.
    Scale bend by the blade height squared; pass the world position as vP.
  - MOTION (the verifier's animates gate): the sway must be CLEARLY visible from the first seconds —
    the verifier samples t ≈ 2-6 s. Tip displacement of a few tenths of the blade height or more; a
    field that barely stirs fails the render gate even if it looks right in a still frame.
  - Fragment: colour root→tip from uGrassA→uGrassB; light with uSunI * cloudShad(vP); add
    uSunC * shaftMask(vP) glow toward the tips; add FLASH_C * uFlash; end with
    `gl_FragColor = vec4(fog(color, vP), 1.0);` followed by TAIL.

PERFORMANCE: the verifier renders on a CPU rasterizer — <= 45000 instances, <= 4 height segments
per blade, no loops in the fragment shader. Four host states (first-light, cloud-shadows,
storm-break, gold-dusk) set the colours and wind; your job is the field's TECHNIQUE.
Rules: procedural only; one InstancedMesh; <= ~90 lines; runs clean in three.js r169.

BRIEF: {brief}

Output ONLY a single ```js fenced ES module. Nothing before or after the fence."""
