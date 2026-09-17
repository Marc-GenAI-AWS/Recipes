"""Ocean-layer contract for the seastate host (open ocean from a ship's bow).

Written for a model that has never seen this scene: it states the whole API surface the layer may use, because seastate is
a different host from highpark — no terrain, no groundH, a different prelude and a 20-state weather/time cycle.
Prose, not example code: contract examples get copied verbatim (the vegetation `vec2 dir` lesson, 2026-09-15).
"""

OCEAN_PROMPT = """You are writing ONE layer of a procedural Three.js scene called "Sea State": open ocean seen from a ship's
bow, no land in sight. Your layer is the WATER SURFACE. The sky dome, rain and camera are written by others and are frozen.

Output a single ES module that exports `class Ocean`. It is constructed once with a context object and then updated every
frame:

  constructor(ctx)   ctx = { THREE, scene, camera, renderer, U, cur, rnd }
  update(dt, t)      dt = seconds since the last frame, t = seconds since start

Build all geometry and materials in the constructor and add them to ctx.scene. Never create geometry, materials or
textures inside update() — mutate uniforms instead.

STORE THE CONTEXT: update() is called with only (dt, t), so the constructor MUST keep what it will need later — assign
`this.ctx = ctx` (and keep references to your material and geometry on `this`). Reading `this.ctx` in update() without
having assigned it throws "Cannot read properties of undefined (reading 'cur')" on the first frame and nothing renders.

IN SCOPE (import from '../prelude.glsl.js', no other imports needed):
  atmosphereUniformsGLSL   a GLSL string declaring the shared uniforms — concatenate it FIRST in your fragment shader
  atmosphereGLSL           a GLSL string of shared helpers — concatenate it SECOND, after the uniforms string
and from '../../contract/runtime.js':
  uniformsFor(U, extra)    merges the shared uniform bag U with your own extra uniforms; pass the result as `uniforms`

REQUIRED SHADER DEFINE: the shared helper string contains a loop bounded by the preprocessor symbol CLOUD_OCT, which it does
NOT declare. Any ShaderMaterial that concatenates it must supply that symbol itself, by passing a `defines` object on the
material with CLOUD_OCT set to a small positive integer (3 is a good value for water reflections; higher costs more). Omit
this and the fragment shader fails to compile with "'CLOUD_OCT' : undeclared identifier" and nothing renders.

GLSL HELPERS available once those two strings are concatenated (do NOT redefine them):
  vec3 skyRadiance(vec3 dir)   the sky colour in a direction — use it for reflections so the water mirrors the real sky
  vec4 cloudLayer(vec3 dir)    the cloud deck in a direction
  vec3 starField(vec3 dir)     night stars
  vec3 acesTonemap(vec3 x)     tone mapping — apply before the gamma step
  float vnoise(vec2 p)         value noise — takes a vec2, so pass a 2D slice such as a world xz position
  float fbm(vec2 p)            fractal noise — also vec2; animate it by adding a time-scaled offset to that vec2
  float hash21(vec2 p)         cheap hash, useful for dither

SHARED UNIFORMS — ALREADY DECLARED, DO NOT DECLARE OR ADD THEM AGAIN. The prelude's uniform string declares uTime,
uExposure, uSunDisc, uSunGlow, uGradFalloff, uCloudCoverage, uCloudDensity, uCloudScale, uFogVeil, uStars, uMoon and
uLightning; the shared bag U additionally carries uSunDir, uSunTint, uZenith, uHorizon, uFogColor, uCloudLit, uCloudShadow
and uMoonDir. Read any of them in your shader. Writing `uniform vec3 uSunDir;` (or any other name above) in your own shader
source is a compile error — "'uSunDir' : redefinition" — and passing one of those names in the `extra` object of
uniformsFor() does the same. Your extras must use NEW names only, for values the host does not already publish.

GLSL TYPE DISCIPLINE (these are the errors that most often kill this layer):
  - vnoise and fbm take a vec2. A vec2 has ONLY .x and .y — writing .z or .xyz on one is "vector field selection out of
    range". To use a 3D position with them, pass a 2D slice such as worldPos.xz.
  - Only vectors can be swizzled; a float has no .x, and nothing that is not a vector/struct has .xyz.
  - Declare a varying in BOTH the vertex and fragment shader with the same type, or the program will not link.

PER-STATE VALUES on ctx.cur, refreshed by the host every frame — read these in update() and push them into your own
uniforms so the water changes with the weather and time of day:
  cur.ampMul      overall wave amplitude multiplier
  cur.chopMul     how choppy/steep the surface is
  cur.speedMul    how fast the sea evolves
  cur.waterDeep   THREE.Color, the deep-water body colour
  cur.waterShallow THREE.Color, the colour where light passes through thin crests
  cur.foamAmount  0..1 how much foam
  cur.detail      0..1 fine surface ripple strength
  cur.spec        specular strength
  cur.specPower   specular exponent (large = tighter glitter)
  cur.fogDensity  distance fog density
  cur.exposure    scene exposure

REQUIRED BEHAVIOUR:
  - The water must FILL the lower part of the frame out to the horizon. The camera sits about 13 units above the surface
    at the bow, pitched slightly down, so the mesh must extend far enough (thousands of units) that it meets the sky at a
    clean horizon line with no gap and no visible mesh edge.
  - The surface must be animated: waves must visibly move within any 4 seconds. Keep your own wave-time accumulator, add
    dt * cur.speedMul to it in update(), and WRITE IT BACK into your own uniform on every single update() call. A shader
    that reads a uniform nobody updates renders a frozen sea and fails: "scene does not evolve over time".
  - MAKE THE BRIEF VISIBLE. The brief's sea state must change what is rendered, not just the colours: a rough or gale sea
    needs large wave amplitude and steep, short, closely-spaced crests; a glassy calm needs low amplitude and long, smooth
    swells. Foam coverage must follow the brief's foam clause, and the water colour must follow its water clause. Two
    layers written from a calm brief and from a storm brief should be obviously different pictures.
  - Sum several travelling wave components with different directions, wavelengths and speeds so the sea never looks like a
    single sine. Vertical displacement belongs in the vertex shader; fine ripple detail belongs in the fragment normal.
  - Shade with a Fresnel mix: reflect skyRadiance() at grazing angles, show the deep water colour when looking straight
    down, and let the shallow colour read in thin or backlit crests. Add specular from the sun using cur.spec/cur.specPower.
  - Foam should follow the wave shape (steep crests or high displacement), scaled by cur.foamAmount.
  - Apply distance fog with cur.fogDensity so the far sea blends into the horizon haze.
  - Finish the fragment with acesTonemap, then a gamma step, then assign gl_FragColor. If you never assign gl_FragColor the
    surface renders black.

RULES: procedural only — no textures, no asset loading, no external files. No lights, no DOM, no post-processing passes.
Every THREE class must be constructed with `new` (new THREE.Mesh(...), new THREE.BufferGeometry(...)). Read only the ctx
fields listed above; ctx has no other members, and reading one that does not exist throws "Cannot read properties of
undefined". Keep it under about 160 lines. Must run clean in three.js r169 with no console errors. Concentrate vertex density near the
camera rather than using one uniform dense grid — a very large uniform grid will be too slow.

BRIEF: {brief}

Output ONLY a single ```js fenced ES module. Nothing before or after the fence."""
