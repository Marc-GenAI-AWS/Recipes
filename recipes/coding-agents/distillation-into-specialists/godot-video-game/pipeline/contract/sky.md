# Sky specialist contract (v1.1)

You write ONE file: the sky layer of a procedural Godot 4 scene. It owns the
sky dome, the sun (the scene's only directional light), ambient light, fog,
tonemapping and clouds. It publishes the scene palette other layers read.
It never touches any other layer and never edits the contract.

## Engine and target

- Godot 4.7, GDScript, **GL Compatibility renderer** (the build runs in the
  browser). No SSR, no SDFGI, no volumetric fog, no subsurface scattering.
  `Environment.fog_*`, `ProceduralSkyMaterial`, `DirectionalLight3D` shadows
  and `Sprite3D` billboards are all fine.
- Budget: the layer adds at most 40 draw calls and must not drop the scene
  below 60 fps at 1280x720 on a mid GPU. Clouds are billboards or a merged
  mesh, never hundreds of separate nodes.
- The world loops every 200 m along -Z. Sky nodes are far away and static,
  so `on_world_wrapped` is usually a no-op for this layer.

## Base class (game/core/layers/scene_layer.gd)

```gdscript
class_name SceneLayer
extends Node3D
var ctx: WorldContext          # set before build()
func build() -> void            # create nodes under self
func tick(_delta: float) -> void
func on_world_wrapped(_dz: float) -> void
```

Your file must start exactly with `extends SceneLayer` and must NOT declare
`class_name` (the verifier swaps it in by path).

## World context fields you may use

Read:
- `ctx.time: float` seconds since start, `ctx.wind: Vector2` (x is the drift
  direction along world X), `ctx.cloud_tex: ImageTexture` (a soft white
  cloud sprite, 256x256, alpha), `ctx.cloud_cover_tex: ImageTexture` (a
  1024x512 equirectangular panorama of white cloud shapes with alpha, made
  for `ProceduralSkyMaterial.sky_cover`), `ctx.mat(color, roughness)`.

Write (the palette; set them in `build()` before creating nodes, other layers
read them during their own build):
- `ctx.sky_zenith: Color`, `ctx.sky_horizon: Color`
- `ctx.sun_dir: Vector3` unit vector of the light's travel direction
  (pointing DOWN for a sun above the horizon; `sun_dir.y < 0`)
- `ctx.sun_color: Color`, `ctx.fog_color: Color`

Everything else in the context is another segment's business. Do not call
`OS`, `FileAccess`, `DirAccess`, `HTTPRequest`, `JavaScriptBridge`,
`get_tree().quit()`, `load()` or `preload()`.

## Conventions

- Sun elevation and azimuth come from the brief and describe where the sun
  sits in the sky. Elevation is the angle above the horizon; azimuth is
  compass degrees where 0 = the sun is ahead, towards -Z (down the scene),
  90 = towards +X (the sea side on the beach, the right kerb on the street),
  180 = behind the walker. `rotation_degrees = Vector3(-elevation, azimuth_yaw, 0)` on the
  light with `azimuth_yaw = 180 - azimuth` gives a light travelling towards
  the scene; compute `ctx.sun_dir` from the light's basis after adding it to
  the tree (`-basis.z`), with a hand-computed fallback.
- Shadows in the Compatibility renderer are always hard-edged
  (`light_angular_distance` does nothing). Soft light is therefore expressed
  by turning the sun's `shadow_enabled` off (overcast, heavy haze, night) or
  keeping its energy low relative to ambient, never by shadow softness.
- Ambient fill: keep `AMBIENT_SOURCE_SKY` but set `ambient_light_color` to a
  desaturated version of the horizon colour and `ambient_light_sky_contribution`
  around 0.3 (as the gold does). With the sky dome as the only fill, shadows
  and white surfaces turn saturated blue.
- Night briefs have a negative sun elevation (the sun is below the horizon);
  place the moon, the directional light, 15 to 45 degrees above the horizon
  at the brief's azimuth. The moon is the directional light (cool colour,
  energy 0.25 to 0.45, shadows off or energy under 0.3 so they stay faint), plus
  `ambient_light_energy` of at least 0.35 and exposure 1.0 to 1.3 so the
  ground, props and people stay readable: never large regions crushed to
  black. Sky colours stay above about 0.03 per channel. Fog is cool and
  visible.
- Dusk and dawn briefs: the sun sits at or just under the horizon. Give the
  sky a distinct band: a saturated orange/magenta `sky_horizon_color`, an
  indigo or violet `sky_top_color`, a low `sky_curve` (0.03 to 0.06) so the
  band stays thin, and a visible sun disc (`sun_angle_max` 4 to 10 degrees
  with `sun_curve` 0.05 to 0.2). Light energy 0.4 to 0.8, long soft shadows.
- Haze: distance fog with `fog_density` scaled with the brief's haze, about
  0.0003 at haze 0 up to 0.006 at haze 1 (distant buildings must visibly
  soften above haze 0.5), `fog_sky_affect` 0.1 to 0.5, fog colour close to
  the horizon colour. `fog_aerial_perspective` 0.3 to 0.7 helps at high haze.
- Use `Environment.TONE_MAPPER_FILMIC` and a modest exposure (0.7 to 1.0 by
  day, higher at night as above).
- Clouds come in two techniques, chosen by cover:
  - Cover below about 0.5: distinct cumulus as `Sprite3D` billboards with
    `ctx.cloud_tex`, unshaded, on a ring 500 to 950 m away at 70 to 190 m
    height, drifting with `ctx.wind` and wrapping at +/-950 m. Roughly 40
    sprites per unit of cover, tinted by the sun colour (warm at golden hour,
    grey-blue at night). Scale and alpha vary per sprite.
  - Cover 0.5 and above: a textured cloud sheet on the sky itself:
    `sky_mat.sky_cover = ctx.cloud_cover_tex` and
    `sky_mat.sky_cover_modulate = Color(r, g, b, cover)` where the RGB is the
    cloud colour (light grey by day, sun-tinted at the edges of the day, dark
    blue-grey at night). The sheet is a panorama of soft cloud shapes with
    alpha, so at 0.6 it reads as broken cloud with gaps and at 0.95 as a
    near-solid overcast with visible texture. Also flatten and grey the
    zenith and horizon colours, lower the sun energy (overcast: 0.3 to 0.5
    with `shadow_enabled = false`; broken: 0.6 to 0.9 with shadows) and
    raise `ambient_light_energy` to 0.8 to 1.1. Add a few sprites too so the cover has depth. A plain flat grey
    sky with no cloud texture is a failure.
- Deterministic: seed any RandomNumberGenerator.
- The project treats GDScript warnings as errors: give every variable an
  explicit type or a typed initialiser (`var n := 3`, `var c: Color = ...`),
  never infer from a Variant (e.g. from `Array` lookups or `Dictionary`
  values without a type); avoid shadowing variable names in nested scopes.

## Capture recipe (what the verifier renders)

Three 1280x720 frames from the chase camera in the named world: the default
view at 3 s, a tilted-up view at 6 s (more sky), a side view at 9 s. The judge
scores time of day, cloud cover, haze, palette coherence, sun/shadow
direction, and artifacts against the brief.

## Gold example (the shipped sky layer for a clear tropical noon)

```gdscript
extends SceneLayer

# Sky dome, sun, fog/tonemapping and drifting cloud sprites.

var clouds: Array[Sprite3D] = []
var cloud_speed: Array[float] = []


func build() -> void:
	var env := Environment.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = ctx.sky_zenith
	sky_mat.sky_horizon_color = ctx.sky_horizon
	sky_mat.sky_curve = 0.09
	sky_mat.ground_bottom_color = Color(0.4, 0.45, 0.5)
	sky_mat.ground_horizon_color = Color(0.68, 0.82, 0.96)
	sky_mat.sun_angle_max = 8.0
	sky_mat.sun_curve = 0.2
	var sky := Sky.new()
	sky.sky_material = sky_mat
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	# Ambient: mostly a desaturated daylight grey-blue with a little of the
	# sky's own colour, so shadows and white surfaces do not turn saturated
	# blue (the sky dome's zenith on its own is far too blue as fill light).
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_color = ctx.sky_horizon.lerp(Color(0.78, 0.78, 0.78), 0.5)
	env.ambient_light_sky_contribution = 0.3
	env.ambient_light_energy = 0.5
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 0.82
	env.fog_enabled = true
	env.fog_light_color = ctx.fog_color
	env.fog_density = 0.0006
	env.fog_sky_affect = 0.15
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.12
	env.adjustment_contrast = 1.06
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = ctx.sun_color
	sun.light_energy = 1.15
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	sun.directional_shadow_split_1 = 0.2
	sun.directional_shadow_max_distance = 90.0
	sun.directional_shadow_fade_start = 0.85
	sun.shadow_bias = 0.08
	sun.shadow_normal_bias = 2.0
	sun.rotation_degrees = Vector3(-58, 40, 0)
	add_child(sun)
	ctx.sun_dir = -sun.global_transform.basis.z if sun.is_inside_tree() else Vector3(-0.35, -0.8, -0.35)

	var rng := RandomNumberGenerator.new()
	rng.seed = 77
	for i in 16:
		var s := Sprite3D.new()
		s.texture = ctx.cloud_tex
		s.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		s.shaded = false
		s.transparent = true
		s.pixel_size = rng.randf_range(0.6, 1.1)
		var ang := rng.randf_range(-PI, PI)
		var dist := rng.randf_range(500.0, 950.0)
		s.position = Vector3(cos(ang) * dist, rng.randf_range(70.0, 190.0), sin(ang) * dist)
		s.modulate = Color(1, 1, 1, rng.randf_range(0.8, 1.0))
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(s)
		clouds.append(s)
		cloud_speed.append(rng.randf_range(0.6, 1.6))


func tick(delta: float) -> void:
	for i in clouds.size():
		var c := clouds[i]
		c.position.x += ctx.wind.x * cloud_speed[i] * delta
		if c.position.x > 950.0:
			c.position.x = -950.0
```

## Output format

Reply with exactly one fenced code block tagged `gdscript` containing the
complete file, and nothing else.
