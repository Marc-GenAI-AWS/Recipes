# Props specialist contract (v1)

You write ONE file: the props (furniture and street furniture) layer for the
world named in the brief. On the beach that is loungers, umbrellas, towels
and clutter, and it must expose the `spots` the crowd layer seats people on.
On the street it is lamps, power poles and wires, signs, bins, hydrants, a
mailbox and a bench. It never touches any other layer.

## Engine and target

- Godot 4.7, GDScript, GL Compatibility renderer (runs in the browser).
- Budget: all static geometry of a chunk merged with `MeshBatch` into a few
  draw calls (one per material); at most about 12 draw calls per chunk.
  Spots and lamp glow may be extra nodes. 60 fps at 1280x720.
- The world repeats every 200 m along Z. You subclass `ChunkedLayer`; the
  base builds three identical chunks by calling `build_chunk` with the same
  seeded RNG. Chunk-local `z in [-CHUNK, 0)`; never use absolute Z.

## Base classes (game/core/layers)

```gdscript
class_name SceneLayer extends Node3D
var ctx: WorldContext
func build() -> void
func tick(_delta: float) -> void

class_name ChunkedLayer extends SceneLayer
var seed_v := 1                       # set in _init()
var chunks: Array[Node3D]
func build_chunk(chunk: Node3D, rng: RandomNumberGenerator) -> void   # you implement this
```

Your file must start exactly with `extends ChunkedLayer`, set `seed_v` in
`_init()`, and must NOT declare `class_name`. If you override `build()` to
prepare materials, call `super.build()` at its end.

## Batching (game/core/layers/mesh_batch.gd)

```gdscript
var b := MeshBatch.new()
b.add_box_at(size: Vector3, color: Color, pos: Vector3)
b.add_box(size: Vector3, color: Color, xform: Transform3D)
b.add_cylinder(r_top, r_bot, h, color, xform: Transform3D, segments := 10)
b.add(mesh: Mesh, xform: Transform3D, color: Color)        # any Mesh
b.is_empty() -> bool
b.instance(parent: Node3D, name := "Batch", rough := 0.85) -> MeshInstance3D   # flat vertex colours
var mi := MeshInstance3D.new(); mi.mesh = b.commit_with(material); parent.add_child(mi)   # your material
```

`Label3D` is allowed for lettering (signs); keep `double_sided = false` and
face it toward +Z (the player approaches from +Z).

## World context you may use

- `ctx.ground_height(x, z)` (beach sand height; street ground is 0 and the
  sidewalk top is `StreetContext.KERB_H` = 0.15), `ctx.add_obstacle(global_pos,
  radius)` for every item a person could walk into (loungers 1.05, umbrellas
  are inside the lounger obstacle, lamps 0.3, bins 0.45, hydrants 0.3).
  Obstacles need GLOBAL positions: `chunk.global_transform * Vector3(x, 0, z)`.
- `ctx.mat(color, roughness)`, `ctx.noise_tex`, `WorldContext.CHUNK`.
- Beach world (`BeachContext`): walker heads -Z along the shore; sea at +X;
  promenade deck at x = `BOARDWALK_X` (-56). Furniture rows run parallel to
  the shore at x between -36 and -12 (row x values like -13, -18, -23, -28,
  -34), items face the sea (+X). Keep x > -12 clear (the walking beach) and
  never place on the deck.
- Street world (`StreetContext`): road |x| < `ROAD_HALF` (6), sidewalk 6 to
  `WALK_OUT` (9), verge 9 to `VERGE_OUT` (12.5), lots from `LOT_X` (13.5).
  Street furniture stands on the sidewalk near the kerb (x = side * 6.9),
  power poles on the verge (x = side * 10.2); nothing on the road.

## The spots interface (beach only, the crowd depends on it)

```gdscript
var spots: Array = []   # one entry per chunk, in build order: Array of {"node": Node3D, "kind": "lounger" | "towel"}
```

For every lounger or towel, add an empty `Node3D` child under the item's
group node whose transform faces the sea (`Transform3D(Basis(Vector3.UP,
-PI * 0.5), Vector3.ZERO)` relative to a group node placed at the item's
ground position), and append `{"node": spot, "kind": ...}` to that chunk's
list. Append the chunk's list to `spots` at the end of `build_chunk`. The
crowd lies people on loungers (seat height 0.38 m, backrest tilted 0.85 rad)
and sits them on towels (0.02 m thick), using exactly the geometry in the
gold example, so keep those dimensions when you make loungers and towels.
A chunk exposes one spot per lounger or towel; the gold example makes about
180 per chunk (five rows, occupancy 0.5 to 0.7). Density words: sparse 90 to
140 spots per chunk, normal 140 to 220, dense 200 to 300.

Forbidden: `OS`, `FileAccess`, `DirAccess`, `HTTPRequest`, `JavaScriptBridge`,
`get_tree().quit()`, `load()`, `preload()`, `class_name`, absolute Z.

## Conventions

- Deterministic: only use the `rng` you are given.
- The project treats GDScript warnings as errors: explicit types everywhere
  (`var n := 3`, `var c: Color = ...`), no inference from Variant (typed
  Array / Dictionary lookups), no shadowed names, one declaration per name
  per scope.
- Everything rests on the ground: y from `ctx.ground_height` on the beach,
  `KERB_H` on the street sidewalk; nothing floats or sinks.
- Palette words in the brief pick fabric / paint colours; keep colours in
  the reference's range (white frames, saturated fabrics, pastel umbrellas
  on the beach; greys, dark green bins, red hydrants on the street).

## Capture recipe (what the verifier renders)

Three 1280x720 frames. Beach: the default chase view at 3 s and views
turned to each side at 6 s and 9 s. Street: the default view along the
sidewalk at 3 s, a low view back along the near kerb toward the crosswalk at
6 s, and a wider view back across both kerbs at 9 s (about 40 m of the
block in all, so repeated items must recur within every 20 to 30 m to be
seen). Numeric checks read placed node positions,
`spots` count (beach), obstacle count, draw calls, and on the beach the
crowd's contact validator (people must rest on loungers and towels within
1 cm). The judge scores density, layout plausibility, item variety, palette,
grounding, and artifacts.

## Gold example: the beach world

```gdscript
extends ChunkedLayer

# Beach furniture modelled on the reference: dense rows of white loungers with
# coloured fabric, large multi-panel umbrellas, towels, buckets, bags and
# balls. Exposes `spots` so the crowd layer can seat people.

var panel_mats: Array[StandardMaterial3D] = []
var spots: Array = []   # per chunk: [{node, kind}] (kind: "lounger" | "towel")


func _init() -> void:
	seed_v = 2468


func build() -> void:
	var sets := [[Color(0.95, 0.25, 0.5), Color(0.98, 0.85, 0.2), Color(0.3, 0.55, 0.9), Color(0.3, 0.75, 0.45)],
		[Color(0.2, 0.5, 0.9), Color(0.95, 0.95, 0.95)], [Color(0.1, 0.35, 0.75), Color(0.2, 0.6, 0.9)],
		[Color(0.95, 0.5, 0.2), Color(0.98, 0.9, 0.5), Color(0.95, 0.3, 0.35)], [Color(0.25, 0.7, 0.5), Color(0.95, 0.95, 0.9)]]
	for cols in sets:
		var m := StandardMaterial3D.new()
		m.albedo_texture = _panel_tex(cols)
		m.roughness = 0.9
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		panel_mats.append(m)
	super.build()


func _panel_tex(cols: Array) -> ImageTexture:
	# 8 panels around the cone, cycling through the colour set
	var img := Image.create(256, 8, false, Image.FORMAT_RGB8)
	for x in 256:
		var c: Color = cols[(x / 32) % cols.size()]
		if x % 32 < 2:
			c = c.darkened(0.3)   # seam
		for y in 8:
			img.set_pixel(x, y, c)
	return ImageTexture.create_from_image(img)


func build_chunk(chunk: Node3D, rng: RandomNumberGenerator) -> void:
	var L := WorldContext.CHUNK
	var chunk_spots := []
	var fabric := [Color(0.3, 0.55, 0.85), Color(0.2, 0.65, 0.6), Color(0.3, 0.7, 0.45), Color(0.95, 0.95, 0.92), Color(0.9, 0.3, 0.3)]
	# All static geometry of the chunk goes into a few batches: one for flat
	# colours, one per umbrella/towel panel material. Spots stay as empty Node3Ds.
	var flat := MeshBatch.new()
	var panels: Array[MeshBatch] = []
	for m in panel_mats:
		panels.append(MeshBatch.new())
	# Rows parallel to the shore, like the reference, thinning toward the water.
	for row_x in [-13.0, -18.0, -23.0, -28.0, -34.0]:
		var occupancy := 0.7 if row_x < -20.0 else 0.5
		var z := -L + rng.randf_range(0.5, 2.5)
		while z < 0.0:
			if rng.randf() < occupancy:
				var x: float = row_x + rng.randf_range(-1.2, 1.2)
				var g := Node3D.new()
				g.position = Vector3(x, ctx.ground_height(x, z), z)
				g.rotation.y = rng.randf_range(-0.35, 0.35)
				chunk.add_child(g)
				var base := g.transform * Transform3D(Basis(Vector3.UP, -PI * 0.5), Vector3.ZERO)  # faces the sea (+x)
				var spot := Node3D.new()
				spot.transform = Transform3D(Basis(Vector3.UP, -PI * 0.5), Vector3.ZERO)
				g.add_child(spot)
				ctx.add_obstacle(g.global_position, 1.05)
				if rng.randf() < 0.8:
					_lounger(flat, base, fabric[rng.randi() % fabric.size()])
					chunk_spots.append({"node": spot, "kind": "lounger"})
				else:
					var pi := rng.randi() % panels.size()
					panels[pi].add_box(Vector3(0.9, 0.03, 1.9), Color(1, 1, 1), base * Transform3D(Basis.IDENTITY, Vector3(0, 0.02, 0)))
					chunk_spots.append({"node": spot, "kind": "towel"})
				if rng.randf() < 0.28:
					_umbrella(flat, panels, g.transform, rng)
				if rng.randf() < 0.35:
					_clutter(flat, panels, g.transform, rng)
			z += rng.randf_range(2.8, 3.8)
	flat.instance(chunk, "Furniture", 0.75)
	for i in panels.size():
		if not panels[i].is_empty():
			var mi := MeshInstance3D.new()
			mi.name = "Panels%d" % i
			mi.mesh = panels[i].commit_with(panel_mats[i])
			chunk.add_child(mi)
	spots.append(chunk_spots)


func _lounger(batch: MeshBatch, base: Transform3D, fab: Color) -> void:
	var white := Color(0.96, 0.96, 0.96)
	var tilt := Basis.IDENTITY.rotated(Vector3.RIGHT, 0.85)
	batch.add_box(Vector3(0.66, 0.05, 1.3), fab, base * Transform3D(Basis.IDENTITY, Vector3(0, 0.38, 0.15)))
	batch.add_box(Vector3(0.66, 0.05, 0.75), fab, base * Transform3D(tilt, Vector3(0, 0.6, -0.78)))
	for dx in [-0.36, 0.36]:
		batch.add_box(Vector3(0.05, 0.07, 1.5), white, base * Transform3D(Basis.IDENTITY, Vector3(dx, 0.38, 0.1)))
		batch.add_box(Vector3(0.05, 0.07, 0.8), white, base * Transform3D(tilt, Vector3(dx, 0.62, -0.8)))
		for dz in [-0.6, 0.7]:
			batch.add_box(Vector3(0.05, 0.38, 0.05), white, base * Transform3D(Basis.IDENTITY, Vector3(dx, 0.19, dz)))
	batch.add_box(Vector3(0.7, 0.05, 0.05), white, base * Transform3D(Basis.IDENTITY, Vector3(0, 0.2, 0.7)))


func _umbrella(flat: MeshBatch, panels: Array[MeshBatch], base: Transform3D, rng: RandomNumberGenerator) -> void:
	var u := base * Transform3D(Basis.IDENTITY, Vector3(rng.randf_range(-0.6, 0.6), 0, rng.randf_range(-1.8, -1.1)))
	flat.add_box(Vector3(0.06, 2.5, 0.06), Color(0.85, 0.85, 0.85), u * Transform3D(Basis.IDENTITY, Vector3(0, 1.25, 0)))
	var pi := rng.randi() % panels.size()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.0
	cm.bottom_radius = 1.7
	cm.height = 0.65
	cm.radial_segments = 16
	cm.cap_bottom = false
	var tilt := Basis.IDENTITY.rotated(Vector3.FORWARD, rng.randf_range(-0.1, 0.1))
	panels[pi].add(cm, u * Transform3D(tilt, Vector3(0, 2.45, 0)), Color(1, 1, 1))
	var vm := CylinderMesh.new()
	vm.top_radius = 1.7
	vm.bottom_radius = 1.75
	vm.height = 0.2
	vm.radial_segments = 16
	vm.cap_top = false
	vm.cap_bottom = false
	panels[pi].add(vm, u * Transform3D(tilt, Vector3(0, 2.02, 0)), Color(1, 1, 1))


func _clutter(flat: MeshBatch, panels: Array[MeshBatch], base: Transform3D, rng: RandomNumberGenerator) -> void:
	var r := rng.randf()
	var at := Vector3(rng.randf_range(-1.0, 1.0), 0.0, rng.randf_range(1.2, 1.8))
	if r < 0.35:
		flat.add_cylinder(0.22, 0.18, 0.4, Color(0.95, 0.2, 0.6), base * Transform3D(Basis.IDENTITY, at + Vector3(0, 0.2, 0)), 10)   # pink bucket
	elif r < 0.6:
		var cc: Color = [Color(0.2, 0.4, 0.8), Color(0.9, 0.9, 0.9), Color(0.8, 0.2, 0.2)][rng.randi() % 3]
		flat.add_box(Vector3(0.5, 0.4, 0.35), cc, base * Transform3D(Basis.IDENTITY, at + Vector3(0, 0.2, 0)))   # cooler
	elif r < 0.8:
		var sm := SphereMesh.new()
		sm.radius = 0.24
		sm.height = 0.48
		sm.radial_segments = 12
		sm.rings = 6
		var rb := Basis.from_euler(Vector3(rng.randf(), rng.randf(), rng.randf()))
		panels[rng.randi() % panels.size()].add(sm, base * Transform3D(rb, Vector3(rng.randf_range(-1.5, 1.5), 0.24, rng.randf_range(-2.0, 2.0))), Color(1, 1, 1))
	else:
		flat.add_box(Vector3(0.35, 0.3, 0.2), Color(0.9, 0.6, 0.15), base * Transform3D(Basis.IDENTITY, at + Vector3(0, 0.15, 0)))   # bag
```

## Gold example: the street world (abridged to its pattern)

```gdscript
extends ChunkedLayer

# Street furniture: lamps with glowing heads, power poles with sagging wires,
# a STOP sign with real lettering, bins, hydrants, a mailbox, a bus bench.

var lamp_glow: StandardMaterial3D


func _init() -> void:
	seed_v = 3131


func build() -> void:
	lamp_glow = StandardMaterial3D.new()
	lamp_glow.albedo_color = Color(1.0, 0.98, 0.9)
	lamp_glow.emission_enabled = true
	lamp_glow.emission = Color(1.0, 0.95, 0.8)
	lamp_glow.emission_energy_multiplier = 0.6
	super.build()


func build_chunk(chunk: Node3D, rng: RandomNumberGenerator) -> void:
	var L := WorldContext.CHUNK
	var sc: StreetContext = ctx as StreetContext
	var b := MeshBatch.new()
	var glow := MeshBatch.new()
	var grey := Color(0.32, 0.34, 0.36)
	for side: float in [-1.0, 1.0]:
		var x := side * (sc.ROAD_HALF + 0.9)
		var z := -L + 6.0
		var i := 0
		while z < 0.0:
			if i % 2 == 0:
				# lamp: tapered pole, curved arm, glowing head
				b.add_cylinder(0.07, 0.13, 8.0, grey, Transform3D(Basis.IDENTITY, Vector3(x, 4.0 + sc.KERB_H, z)), 8)
				b.add_box(Vector3(1.8, 0.1, 0.1), grey, Transform3D(Basis.IDENTITY.rotated(Vector3.FORWARD, side * 0.25), Vector3(x - side * 0.85, 8.1 + sc.KERB_H, z)))
				b.add_box_at(Vector3(0.6, 0.12, 0.34), grey, Vector3(x - side * 1.75, 8.0 + sc.KERB_H, z))
				glow.add_box_at(Vector3(0.5, 0.05, 0.28), Color(1, 1, 1), Vector3(x - side * 1.75, 7.93 + sc.KERB_H, z))
				ctx.add_obstacle(chunk.global_transform * Vector3(x, 0, z), 0.3)
			if i % 6 == 3:   # bin
				b.add_cylinder(0.3, 0.3, 0.9, Color(0.2, 0.35, 0.25), Transform3D(Basis.IDENTITY, Vector3(x, 0.45 + sc.KERB_H, z + 1.5)), 10)
				ctx.add_obstacle(chunk.global_transform * Vector3(x, 0, z + 1.5), 0.45)
			if i % 8 == 5:   # hydrant
				var hc := Color(0.85, 0.15, 0.12)
				b.add_cylinder(0.12, 0.14, 0.7, hc, Transform3D(Basis.IDENTITY, Vector3(x, 0.35 + sc.KERB_H, z - 2.0)), 8)
				ctx.add_obstacle(chunk.global_transform * Vector3(x, 0, z - 2.0), 0.3)
			z += 12.0
			i += 1
	# power poles on the +X verge every 36 m with wires between them, a STOP
	# sign (Label3D "STOP", facing +Z) and street-name plate near the chunk
	# start, a bus bench and a mailbox on the sidewalks, then:
	b.instance(chunk, "StreetProps", 0.8)
	var gmi := MeshInstance3D.new()
	gmi.mesh = glow.commit_with(lamp_glow)
	chunk.add_child(gmi)
```

## Output format

Reply with exactly one fenced code block tagged `gdscript` containing the
complete file for the brief's world, and nothing else.
