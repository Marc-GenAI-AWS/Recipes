# Water specialist contract (v1.1)

You write ONE file: the sea layer of the beach world. It is one large flat
grid mesh at sea level with a shader that does the swell, the depth colour,
the shallows over sand, the foam at the water's edge and breaker lines
further out. It never touches any other layer.

## Engine and target

- Godot 4.7, GDScript, GL Compatibility renderer (runs in the browser): no
  SSR, no refraction buffer, no screen-space effects. Transparency onto the
  sand is faked in the shader by mixing toward `sand_color` where the water
  is shallow. The shader is `shader_type spatial` and may displace `VERTEX`
  in `vertex()` (the swell) and set `ALBEDO / ROUGHNESS / SPECULAR / NORMAL`.
- Budget: one draw call, 60 fps at 1280x720.
- The world repeats every 200 m along Z. The mesh spans z from
  `-CHUNK * 2.4` to `CHUNK * 1.4` so the loop never shows an edge. Use only
  `TIME` and world-space XZ in the shader so animation tiles seamlessly.

## Base class and helpers (game/core/layers)

```gdscript
class_name SceneLayer extends Node3D
var ctx: WorldContext
func build() -> void
func tick(_delta: float) -> void
func grid_mesh(x0: float, x1: float, z0: float, z1: float, step: float, height_fn: Callable) -> ArrayMesh
```

Your file must start exactly with `extends SceneLayer` and must NOT declare
`class_name`.

## Shader: set knobs, do not write shader code

Load the shipped water shader (`res://segments/water/shaders/water.gdshader`)
and set its uniforms; do NOT write shader code (`Shader.new()`,
`shader.code`, `load()` of anything else) - the verifier rejects it. The
shader already does the swell, depth colour, sand show-through, the three
edge zones and the breaker lines; you choose the values:

- `noise_tex` (use `ctx.noise_tex`), `sand_slope` (`BeachContext.SAND_SLOPE`),
  `tide_amp` (0.14; keep it),
- colours `deep_color`, `shallow_color`, `sand_color` (pass `Color(r, g, b)`
  values, never `Vector3`: a raw vec3 skips the sRGB conversion and renders
  neon-bright),
- `swell_amp` (0.3 calm .. 1 gentle .. 2 choppy), `chop` (0 glassy .. 1.5;
  below 1 the surface glasses over, above 1 whitecaps fleck the open water),
- `foam_amount` (0 none .. 1 lacy band .. 2 heavy; it sets how wide the edge
  band and streaks reach, and the band stays lacy even when heavy),
  `breaker_strength` (0 none .. 1.5; sets how wide the breaker lines are),
  `breaker_spacing` (0.5 tight .. 2 wide),
- `clarity_depth` (0.3 murky .. 1 .. 3 sand visible far out), `sparkle` (0..1.5).

## World context you may use

- Sea is at +X. The sand under the water is at `y = -BeachContext.SAND_SLOPE
  * x` (SAND_SLOPE = 0.06), so water depth at a point is
  `y_water + sand_slope * x`. The mesh spans x from -12 (under the wet sand,
  hidden) to +520 and z as above, 3 m step, height 0 (the shader adds tide
  and swell).
- `ctx.time`, `ctx.noise_tex`, `ctx.sky_horizon`, `WorldContext.CHUNK`.
  The sea level is `ctx.sea_level()` = `0.14 * sin(t * 0.55) + 0.05 * sin(t
  * 1.7)`; the world's wet line (`ctx.tide_reach`) sits 2.5 m up the beach
  from where that level meets the sand slope. The shader's tide term
  `tide_amp * sin(TIME * 0.55) + 0.05 * sin(TIME * 1.7)` is what makes the
  water's edge and the wet sand agree, so keep `tide_amp` at 0.14 and those
  frequencies.

Forbidden: `OS`, `FileAccess`, `DirAccess`, `HTTPRequest`, `JavaScriptBridge`,
`get_tree().quit()`, `preload()`, `load()` of anything but the water shader,
`Shader.new()`, `shader.code`, `class_name`.

## Conventions

- The project treats GDScript warnings as errors: explicit types
  everywhere, no inference from Variant, no shadowed names.
- Brief words: sea state sets `swell_amp` and `chop` (calm 0.3 / 0.2,
  gentle 1 / 1, choppy 1.8 / 1.5) and `breaker_strength` (calm 0.2, gentle 1,
  choppy 1.4); colour words set `deep_color` and `shallow_color` (turquoise
  tropical 0/0.16/0.42 and 0.02/0.34/0.46; deep navy 0/0.03/0.15 and
  0.01/0.1/0.28; grey-green temperate 0.1/0.16/0.13 and 0.22/0.28/0.22; milky
  jade 0.1/0.28/0.2 and 0.35/0.52/0.36; clear aquamarine 0/0.22/0.36 and
  0.08/0.48/0.46). These values are calibrated against renders of this
  scene: its sky reflection and fog add blue and lift everything, so greens
  need less blue and navy needs darker values than the words suggest. Foam
  words set `foam_amount` (little 0.4, lacy 1, heavy
  1.8); clarity words set `clarity_depth` (murky 0.35, only at the edge 1,
  far out 2.5).
- Keep the three-zone water's edge from the reference: a thin dark
  reflective wash film, a dense lacy foam band, then sparse lace streaks.

## Capture recipe (what the verifier renders)

Three 1280x720 frames from the chase camera: the default view at 3 s (the
shoreline runs down the right of the frame); then the walker turns to the
sea and walks to the wet band, and the camera tilts down at their feet at
7 s (wet sand, the water's edge and the shallows fill the frame); then the
camera turns to look along the shore with the sea on the left at 9 s. The
judge also sees the shipped default sea under the same views and scores
colour relative to it (this scene's daylight lightens every colour). It
scores sea state, colour and depth gradient, the water's edge and foam,
breaker lines, and artifacts (seams, flat untextured water, edges of the
mesh, z-fighting with the sand).

## Gold example

```gdscript
extends SceneLayer

# The sea: one big grid with the water shader doing swells, depth colour,
# edge foam and breaker lines.

var material: ShaderMaterial


func build() -> void:
	var flat := func(_x: float, _z: float) -> float: return 0.0
	var mesh := grid_mesh(-12.0, 520.0, -WorldContext.CHUNK * 2.4, WorldContext.CHUNK * 1.4, 3.0, flat)
	material = ShaderMaterial.new()
	material.shader = load("res://segments/water/shaders/water.gdshader")
	material.set_shader_parameter("noise_tex", ctx.noise_tex)
	material.set_shader_parameter("sand_slope", BeachContext.SAND_SLOPE)
	mesh.surface_set_material(0, material)
	var mi := MeshInstance3D.new()
	mi.name = "Water"
	mi.mesh = mesh
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
```

## Output format

Reply with exactly one fenced code block tagged `gdscript` containing the
complete file, and nothing else.
