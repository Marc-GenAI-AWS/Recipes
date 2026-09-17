# Golden scenes

Seven complete, hand-built host scenes. They are the **reference implementations**: the thing generated
layers are compared against, and the thing every per-segment check is calibrated on.

They are not decoration, and they are not sample output. A generated layer is verified by swapping it into
one of these hosts in place of the host's own layer and rendering the result. So the quality of everything
downstream — the checks, the training data, the specialists — is bounded by the quality of these.

| Scene | What makes its contract different |
|---|---|
| `highpark` | A mountain-prairie basin. Open daylight landscape, one sun, wind over turf. |
| `cenote` | A flooded sinkhole. Light enters as a single shaft; caustics; a diver's torch as a second source. |
| `seastate` | Open ocean, 20 states. **Partial host** — ocean, rain and sky only, no full six-segment set. |
| `canyon` | A slot canyon. Most light on a shaded wall arrives *bounced off the opposite sunlit wall*. |
| `glacier` | Alpine ice. Inverted exposure: very bright, low contrast, blue filled shadows, translucent ice. |
| `citynight` | A rain-wet street. **No `uSunDir` at all** — lit by a per-frame array of point emitters. |
| `caldera` | A volcanic caldera. Light comes from the **ground**, so shadows fall upward and the sky is darkest. |

The variety is deliberate. Specialists trained on a single world learn that world; the goal is for them to
learn the *contract*. These hosts disagree with each other about where light comes from, what the medium
is, and what a layer is even for, while sharing one interface.

## The shared interface

Every host exposes the same shape, which is what makes one harness and one contract format work across all
of them:

```
<host>/
  manifest.json      states, the build file list, the ground-height field contract
  scene.js           the state machine; publishes per-state values on ctx.cur
  prelude.glsl.js    shared GLSL: helpers, base shaders, the tonemap tail
  field.js           CPU height field, mirroring the GLSL so geometry and placement agree
  materials.js       material factories built by string-surgery on the base shaders
  camera.js          the viewpoint every layer is judged from
  layers/*.js        the reference layers
contract/runtime.js  the frozen engine all hosts boot against (shared, not per-host)
```

`pipeline/contract/descriptor.py` reads these files and generates the model-facing contract, so a new world
costs an extraction plus a paragraph of intent rather than a hand-written specification that can drift.

## Check one renders before you trust it

```bash
python scripts/render_host.py canyon --shots /tmp/canyon    # expect gate 1.0
```

If a host does not pass on its own, fix that first: a layer cannot be verified against a broken host.

## Honest status

`highpark` and `cenote` are the most mature — they carry the most reference layers and the most calibrated
checks. `canyon`, `glacier`, `citynight` and `caldera` are newer: all pass the structural gates at 1.0 and
render convincingly, but a few of their layers are weaker than the two originals. Known soft spots:
glacier's lichen reads as stipple at camera distance rather than as plants, caldera's soaring birds read as
flat plates at close range, and citynight's `neon-rain` state reads more amber than neon because the sodium
lamps sit over the road while the neon is on the frontages.

`seastate` is a partial host and only ever fed the `ocean` segment; it is included because the ocean
contract and its water-presence check are calibrated against it.
