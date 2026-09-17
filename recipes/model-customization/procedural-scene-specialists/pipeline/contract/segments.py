"""Segment registry: everything layer-specific in one place.

Each segment = (host scene, build file swapped by the layer-harness, the class a
candidate must define, its contract prompt, its brief sampler, its checks). The
generic runner (gen_segment.py), dataset builder and RL trainer read from here,
so adding a segment is a registry entry — not a new copy of the scripts.
"""
from __future__ import annotations

import ground_briefs
import sky_briefs
from gen_sky_baseline import PROMPT as SKY_PROMPT

GENERIC_REPAIR = """Your High Park {layer_name} layer failed the render harness. Fix it with the SMALLEST
change that resolves the observation while keeping the visual intent. Most common causes:
re-declaring a uniform the shared prelude G already declares (delete the duplicate), a GLSL
type/syntax slip, or referencing something not in scope. Keep the same class name, the
contract, and the fragment ending in TAIL.

HARNESS OBSERVATION:
{notes}

YOUR MODULE:
```js
{js}
```

Output ONLY the corrected ES module in a single ```js fence. Nothing else."""

GROUND_PROMPT = """You are a senior Three.js graphics engineer. Write ONE layer of a modular,
single-file real-time scene ("High Park", a mountain-prairie basin under peaks): the PRAIRIE
GROUND — the rolling turf terrain the herd, grass and rocks stand on. Output a single ES module
that exports `class Prairie` and nothing else.

The module is assembled into a FROZEN host scene — you may only build the ground. Contract:

  export class Prairie {
    constructor(ctx) {
      // ctx = { THREE, scene, camera, renderer, U, rnd, rr, cur }
    }
  }

GEOMETRY (REQUIRED — other layers depend on it): build exactly ONE mesh from
`new THREE.PlaneGeometry(1000, 780, 190, 150)`, then `rotateX(-Math.PI / 2)`, then
`translate(0, 0, -160)`, then set EVERY vertex's y to `groundH(x, z)` — the shared height field
that the grass, horses and camera also sample — and `computeVertexNormals()`. Do NOT offset,
scale or add noise to the height. Add the mesh to ctx.scene.

In scope (no import needed; importing is harmless — imports are stripped at assembly):
  - groundH(x, z)          -> the frozen height field. A JAVASCRIPT function only: call it while
                              building the geometry. It does NOT exist in GLSL — never call it
                              inside a shader (the heights are already baked into the vertices).
  - uniformsFor(U, extra)  -> your material's uniforms MUST be built with this.
  - VERT_WORLD             -> vertex shader string providing `varying vec3 vP, vN;` (world
                              position + normal). Use it as your vertexShader. It declares those
                              varyings on the VERTEX side only: your fragment shader must declare
                              `varying vec3 vP, vN;` itself before using them, or the program fails
                              to compile with "'vN' : undeclared identifier".
  - G     -> GLSL prelude; PREPEND to your fragmentShader. It declares uTime, uSkyTop,
             uSkyHorizon, uSunC, uSunI, uSunDir, uFogC, uFogD, uWind, uCloud, uShadowAmt, uShaft,
             uFlash, uShaftDir, uSaddle and provides hash1(vec3), noise3(vec3), fbm3(vec3),
             fbm2(vec2), windAt(vec2 xz, float t), cloudShad(vec3 p), shaftMask(vec3 p),
             fog(vec3 color, vec3 p), fogAtt(vec3 p), and the constant FLASH_C (vec3).
  - TAIL  -> APPEND to your fragmentShader; it closes main() with tonemapping + colorspace.
NOT in G — declare yourself: `uniform vec3 uGrassA, uGrassB;` (the state's dark/light grass colours).
CRITICAL: do NOT re-declare any uniform G declares (a duplicate is a GLSL "redefinition" error).
GLSL reserved words cannot be variable names — avoid patch, flat, smooth, sample, filter, input,
output, active, common, partition (a reserved word is a GLSL syntax error).

Look: vary the turf with fbm2 over p.xz; light with max(dot(n, normalize(uSunDir)),0) * uSunC *
uSunI * cloudShad(p) so cloud shadows move across it; add uSunC * shaftMask(p) for the light
corridor; a sky ambient from mix(uSkyHorizon, uSkyTop, 0.5); FLASH_C * uFlash for lightning.
The fragment MUST end with `gl_FragColor = vec4(fog(color, vP), 1.0);` followed by TAIL — fog is
what makes the basin recede into the haze.

The four host states (first-light, cloud-shadows, storm-break, gold-dusk) drive the uniforms every
frame; the COLOURS come from them — your job is the surface TECHNIQUE.
Rules: procedural only, no textures/assets; one mesh; <= ~100 lines; runs clean in three.js r169.

BRIEF: {brief}

Output ONLY a single ```js fenced ES module. Nothing before or after the fence."""

SEGMENTS: dict[str, dict] = {
    "sky": {
        "scene": "highpark", "layer": "layers/atmosphere.js", "class_name": "Atmosphere",
        "layer_name": "sky", "prompt": SKY_PROMPT, "repair": GENERIC_REPAIR,
        # sky_presence: a dome that never writes gl_FragColor passed greycard + horizon (2026-09-14)
        "briefs": sky_briefs, "checks": ["greycard", "horizon", "sky_presence"],
    },
    "ground": {
        "scene": "highpark", "layer": "layers/prairie.js", "class_name": "Prairie",
        "layer_name": "prairie ground", "prompt": GROUND_PROMPT, "repair": GENERIC_REPAIR,
        "briefs": ground_briefs, "checks": ["greycard", "horizon", "ground_detail"],
    },
}

import camera_briefs  # noqa: E402
from camera_contract import CAMERA_PROMPT  # noqa: E402

SEGMENTS["camera"] = {
    "scene": "highpark", "layer": "camera.js", "class_name": "CameraRig",
    "layer_name": "camera rig", "prompt": CAMERA_PROMPT, "repair": GENERIC_REPAIR,
    "briefs": camera_briefs, "checks": ["greycard", "horizon", "horizon_band"],
}

import vegetation_briefs  # noqa: E402
from vegetation_contract import VEGETATION_PROMPT  # noqa: E402

SEGMENTS["vegetation"] = {
    "scene": "highpark", "layer": "layers/grass.js", "class_name": "Grass",
    "layer_name": "grass field", "prompt": VEGETATION_PROMPT, "repair": GENERIC_REPAIR,
    "briefs": vegetation_briefs, "checks": ["greycard", "horizon", "fine_texture"],
}

import fauna_briefs  # noqa: E402
from fauna_contract import FAUNA_PROMPT  # noqa: E402

SEGMENTS["fauna"] = {
    "scene": "highpark", "layer": "layers/herd.js", "class_name": "Herd",
    "layer_name": "herd", "prompt": FAUNA_PROMPT, "repair": GENERIC_REPAIR,
    "briefs": fauna_briefs, "checks": ["greycard", "horizon", "herd_presence"],
    # Fable exhausted 8000 output tokens with no text on both fauna smoke briefs (2026-09-14)
    "max_tokens": 16000,
}

import effects_briefs  # noqa: E402
from effects_contract import EFFECTS_PROMPT  # noqa: E402

SEGMENTS["effects"] = {
    "scene": "highpark", "layer": "layers/mist.js", "class_name": "Mist",
    "layer_name": "mist", "prompt": EFFECTS_PROMPT, "repair": GENERIC_REPAIR,
    "briefs": effects_briefs, "checks": ["greycard", "horizon", "mist_gating"],
}

# ── seastate host (a SECOND scene: no terrain, no groundH, 20 weather/time states, its own prelude) ──────────────
# Everything above targets highpark. This entry exists to test whether a capable base model can bootstrap layers for a
# host it has never seen, with no fine-tuning and no Fable teacher.
import ocean_briefs  # noqa: E402
from ocean_contract import OCEAN_PROMPT  # noqa: E402

SEGMENTS["ocean"] = {
    "scene": "seastate", "layer": "layers/ocean.js", "class_name": "Ocean",
    "layer_name": "ocean surface", "prompt": OCEAN_PROMPT, "repair": GENERIC_REPAIR,
    "briefs": ocean_briefs, "checks": ["greycard", "horizon", "water_presence"],
    "max_tokens": 12000,
}
