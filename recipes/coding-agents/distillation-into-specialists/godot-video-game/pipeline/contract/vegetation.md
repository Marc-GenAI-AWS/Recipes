# Vegetation specialist contract (v1)

You write ONE file: the vegetation layer for the world named in the brief. It
places trees, palms, hedges and shrubs, using the shared species generators,
and makes crowns sway. It never touches any other layer.

## Engine and target

- Godot 4.7, GDScript, GL Compatibility renderer (runs in the browser).
- Budget: at most about 60 draw calls per chunk. Each palm or tree from the
  species generators is 2 to 3 draw calls; hedges, shrubs and small plants
  must be merged with `MeshBatch` into one draw call per material per chunk.
  The scene must stay above 60 fps at 1280x720.
- The world repeats every 200 m along Z. You subclass `ChunkedLayer`: the
  base builds three identical chunks by calling your `build_chunk` with the
  same seeded RNG, so the world loops seamlessly. Never place anything by
  absolute Z; use the chunk-local range `z in [-CHUNK, 0)`.

## Base classes (game/core/layers)

```gdscript
class_name SceneLayer extends Node3D
var ctx: WorldContext
func build() -> void
func tick(_delta: float) -> void
func on_world_wrapped(_dz: float) -> void

class_name ChunkedLayer extends SceneLayer
var seed_v := 1                       # set in _init(); the chunk RNG seed
var chunks: Array[Node3D]             # the three chunk nodes, z = -200, 0, +200
func build_chunk(chunk: Node3D, rng: RandomNumberGenerator) -> void   # you implement this
```

Your file must start exactly with `extends ChunkedLayer`, set `seed_v` in
`_init()`, and must NOT declare `class_name`. Do not override `build()`
unless you call `super.build()` at the end of it.

## Species generators (game/segments/vegetation/species)

```gdscript
# Palm: curved trunk, alpha-cut fronds, shag on tall ones, coconuts on the
# fuller ones. Registers a 0.45 m obstacle. Returns the crown node so you can
# sway it in tick(). tall = thin fan palm 13-18 m; otherwise coconut palm 7-11 m.
Palm.build(parent: Node3D, pos: Vector3, rng: RandomNumberGenerator, ctx: WorldContext, tall := false) -> Node3D

# Leafy tree: trunk + branches + leaf-card lobes, 5.5-8 m times size.
# Registers a 0.45 m obstacle. Returns nothing.
LeafyTree.build(parent: Node3D, pos: Vector3, rng: RandomNumberGenerator, ctx: WorldContext, size := 1.0) -> void
LeafyTree.leaf_material() -> StandardMaterial3D    # alpha-cut leaf card material, for shrubs
```

`pos` is chunk-local; on the beach pass `ctx.ground_height(x, z) - 0.2` as
the y so the trunk base is buried, on the street the ground is at y = 0.

## Batching (game/core/layers/mesh_batch.gd)

```gdscript
var b := MeshBatch.new()
b.add_box_at(size: Vector3, color: Color, pos: Vector3)
b.add_box(size: Vector3, color: Color, xform: Transform3D)
b.add_cylinder(r_top, r_bot, h, color, xform: Transform3D, segments := 10)
b.add(mesh: Mesh, xform: Transform3D, color: Color)        # any Mesh (QuadMesh leaf cards, SphereMesh...)
b.is_empty() -> bool
b.instance(parent: Node3D, name := "Batch", rough := 0.85) -> MeshInstance3D   # one draw call, flat colours
var mi := MeshInstance3D.new(); mi.mesh = b.commit_with(material); parent.add_child(mi)   # one draw call, your material
```

## World context you may use

- `ctx.ground_height(x, z)`, `ctx.add_obstacle(global_pos: Vector3, radius)`
  for anything you place that the species generators did not (hedges: one
  obstacle per 2 m of length, radius 0.8). Obstacles need GLOBAL positions:
  `chunk.global_transform * Vector3(x, 0, z)`.
- `ctx.time` for sway, `ctx.mat(color, roughness)` material cache,
  `WorldContext.CHUNK` (200.0).
- Beach world (`BeachContext`): the walker heads -Z on sand; sea at +X
  (x > 0 is water), promenade deck at `BeachContext.BOARDWALK_X` (-56), the
  walkable lane is x from -62 to +4. Vegetation belongs on the landward side:
  a line of tall palms just seaward of the deck at x about
  `BOARDWALK_X - 2.5`, a few coconut palms on the upper sand x in [-48, -38],
  hedges behind the deck at x about `BOARDWALK_X - 8.6`. Never place anything
  at x > -12 (the busy beach and the water).
- Street world (`StreetContext`): road |x| < `ROAD_HALF` (6), sidewalk from
  6 to `WALK_OUT` (9), grass verge from 9 to `VERGE_OUT` (12.5), house lots
  from `LOT_X` (13.5) outward, both sides. Trees go in the verge (x = side *
  (9.6 to 12.1)), hedges and shrubs along the lot fronts (x about side *
  12.9), never on the road or sidewalk.

Forbidden: `OS`, `FileAccess`, `DirAccess`, `HTTPRequest`, `JavaScriptBridge`,
`get_tree().quit()`, `load()`, `preload()`, `class_name`, absolute Z.

## Conventions

- Deterministic: only use the `rng` you are given.
- The project treats GDScript warnings as errors: give every variable an
  explicit type or a typed initialiser (`var n := 3`, `var c: Color = ...`),
  never infer from a Variant (Array / Dictionary lookups need a declared
  type); avoid shadowing names in nested scopes; declare each variable once
  per scope.
- Density words in the brief: sparse = 6 to 12 trees per chunk per side,
  normal = 12 to 22, dense = 22 to 40. Species mix words say which generator
  dominates. Size words scale `size` (young 0.7 to 0.9, mature 1.0 to 1.3,
  giant 1.4 to 1.8) and pick `tall` palms or coconut palms.
- Keep crowns swaying: collect the `Palm.build` return values and rotate
  them a few hundredths of a radian in `tick`, as the examples do.

## Capture recipe (what the verifier renders)

Three 1280x720 frames from the chase camera: the default view at 3 s, a view
turned toward the vegetation side at 6 s, and the other side at 9 s. Numeric
checks read where you placed nodes (chunk-local positions), the obstacle
count and the draw-call delta. The judge scores density, species mix, size,
placement plausibility, grounding (no floating or sunken trunks), and
artifacts.

## Gold example: the street world

```gdscript
extends ChunkedLayer

var crowns: Array[Node3D] = []

func _init() -> void:
	seed_v = 5150


func build_chunk(chunk: Node3D, rng: RandomNumberGenerator) -> void:
	var L := WorldContext.CHUNK
	var sc: StreetContext = ctx as StreetContext
	for side: float in [-1.0, 1.0]:
		var z := -L + rng.randf_range(2.0, 8.0)
		while z < 0.0:
			var x := side * (sc.WALK_OUT + 1.6 + rng.randf_range(-0.4, 0.8))
			if rng.randf() < 0.45:
				crowns.append(Palm.build(chunk, Vector3(x, 0.0, z), rng, ctx, true))
			else:
				LeafyTree.build(chunk, Vector3(x, 0.0, z), rng, ctx, rng.randf_range(0.9, 1.4))
			z += rng.randf_range(10.0, 17.0)
		# hedges and low shrubs along lot fronts, as leaf-card clumps on a green core
		var hz := -L
		var hb := MeshBatch.new()
		var shrubs := MeshBatch.new()
		var card := QuadMesh.new()
		card.size = Vector2(0.9, 0.9)
		while hz < 0.0:
			var len := rng.randf_range(5.0, 12.0)
			if rng.randf() < 0.5:
				var hh := rng.randf_range(0.8, 1.3)
				hb.add_box_at(Vector3(0.8, hh, len), Color(0.12, 0.3, 0.12), Vector3(side * (sc.LOT_X - 0.6), hh * 0.5, hz + len * 0.5))
				var n := int(len * 3.0)
				for i in n:
					var p := Vector3(side * (sc.LOT_X - 0.6) + rng.randf_range(-0.45, 0.45), rng.randf_range(0.2, hh + 0.2), hz + rng.randf_range(0.0, len))
					var b := Basis.from_euler(Vector3(rng.randf_range(-0.5, 0.5), rng.randf() * TAU, rng.randf_range(-0.5, 0.5)))
					shrubs.add(card, Transform3D(b, p), Color(1, 1, 1).lerp(Color(0.8, 0.95, 0.75), rng.randf()) * rng.randf_range(0.75, 1.05))
			hz += len + rng.randf_range(2.0, 8.0)
		if not hb.is_empty():
			hb.instance(chunk, "Hedges", 0.95)
			var smi := MeshInstance3D.new()
			smi.mesh = shrubs.commit_with(LeafyTree.leaf_material())
			chunk.add_child(smi)


func tick(_delta: float) -> void:
	var t := ctx.time
	for i in crowns.size():
		var c := crowns[i]
		c.rotation.x = 0.045 * sin(t * 0.9 + i * 1.3)
		c.rotation.z = 0.055 * sin(t * 0.7 + i * 0.7) + 0.03
```

## Gold example: the beach world

```gdscript
extends ChunkedLayer

var crowns: Array[Node3D] = []


func _init() -> void:
	seed_v = 4321


func build_chunk(chunk: Node3D, rng: RandomNumberGenerator) -> void:
	var L := WorldContext.CHUNK
	# Tall, thin fan palms in a line along the promenade (as in the reference)
	var z := -L + rng.randf_range(0.0, 6.0)
	while z < 0.0:
		var x := BeachContext.BOARDWALK_X - 2.5 + rng.randf_range(-0.6, 0.6)
		crowns.append(Palm.build(chunk, Vector3(x, ctx.ground_height(x, z) - 0.2, z), rng, ctx, true))
		z += rng.randf_range(5.5, 8.5)
	# a few fuller coconut palms on the sand
	for i in 3:
		var x := rng.randf_range(-48.0, -38.0)
		var zz := rng.randf_range(-L, 0.0)
		crowns.append(Palm.build(chunk, Vector3(x, ctx.ground_height(x, zz) - 0.2, zz), rng, ctx, false))
	# Hedges along the boardwalk's landward side.
	var hedges := MeshBatch.new()
	var hz := -L
	while hz < 0.0:
		var len := rng.randf_range(6.0, 14.0)
		var hx := BeachContext.BOARDWALK_X - 8.6
		hedges.add_box_at(Vector3(1.2, 1.0, len), Color(0.15, 0.4, 0.17), Vector3(hx, ctx.ground_height(hx, hz) + 0.9, hz + len * 0.5))
		hz += len + rng.randf_range(3.0, 10.0)
	hedges.instance(chunk, "Hedges", 0.95)


func tick(_delta: float) -> void:
	var t := ctx.time
	for i in crowns.size():
		var c := crowns[i]
		c.rotation.x = 0.045 * sin(t * 0.9 + i * 1.3)
		c.rotation.z = 0.055 * sin(t * 0.7 + i * 0.7) + 0.03
```

## Output format

Reply with exactly one fenced code block tagged `gdscript` containing the
complete file for the brief's world, and nothing else.
