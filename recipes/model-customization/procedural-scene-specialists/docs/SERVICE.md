# From a sentence to a scene: the service, and what it takes to generate a *new* world

Two different products hide behind "send in a description, get a scene back":

- **A — variations of a known world.** Same host, new layers. This works today: a one-line theme becomes six briefs, six
  specialists write six layers, the verifier accepts or rejects each, and the survivors assemble into one HTML file.
- **B — a world we have never built.** A canyon, a harbour, a flooded street. This does **not** work today, and the
  blocker is not model quality. It is that our verifier is calibrated against a hand-built reference that, by definition,
  a new world does not have.

The service below serves A now and is shaped so B can be added without rebuilding it.

---

## The request

```
POST /scenes            {"description": "a storm breaking over a high prairie", "host": "highpark"}
  -> 202 {"job": "scn_01H...", "tier": "library|warm|cold", "eta_seconds": 30|210|1200}

GET  /scenes/{job}      -> {"state": "planning|writing|verifying|composing|done|failed",
                            "layers": {"sky": "accepted", "fauna": "generating", ...},
                            "url": "https://.../scn_01H.../scene.html"}       # when done
```

One endpoint, three tiers behind it. The client polls; nothing streams, because a scene is a job, not a request.

## The tiers, and why they exist

Wall clock is dominated by **rendering**, not generation: each scene runs 18–30 headless renders at 100–200 s each, on
CPU. Generation is the cheap half. That asymmetry is what makes the tiers worth having.

| Tier | What actually runs | Latency | Marginal cost |
|---|---|---|---|
| **library** | plan → look up six already-verified layers → assemble → one render | ~30 s | CPU only |
| **warm** | as above, but 1–2 missing layers generated on a resident 8B server | 2–4 min | ~$1/h resident |
| **cold** | full loop, including the 27B for the layer that needs it | 15–20 min | ~$9/h while running |

**The library is the important one.** Briefs come from seeded samplers, so the brief space is bounded and heavily
re-used: a planner choosing from 12 candidates per segment will keep landing on briefs we have already verified. Index
every accepted layer by `(host, segment, brief)` and most requests never touch a GPU.

We already have ~1,800 verified layers sitting in `data/` to seed that index. Be honest with users about what it means: a
library-served scene is a *recombination of verified layers*, not fresh authorship. It is the right default for "show me
what this can do" and the wrong one for "make me something new".

## Topology

Distilling the planner collapsed this more than it looks. The planner is an 8B LoRA on the same base as five of the six
specialists, so **one vLLM server with one base and six adapters serves the planner and every layer but one**.

```
        ┌──────────────┐     ┌─────────────────────────────┐
POST ──▶│  API + queue │────▶│ director (CPU)              │
        └──────────────┘     │  plan → per-segment brief   │
               ▲             │  library lookup             │
               │             │  generate on miss ──────────┼──▶ 8B server + 6 LoRAs   (1 GPU, resident)
        GET ───┘             │  verify each layer ─────────┼──▶ render pool (N × CPU)
                             │  compose → verify composite │
                             │  publish HTML + frames      │──▶ object store
                             └─────────────────────────────┘
                                          │
                                          └─ cold path only ──▶ 27B server (4 GPUs, on demand)
```

Scale the render pool, not the GPU: render slots set wall clock, and they are the cheapest thing in the diagram.

## Degradation, stated up front

Every layer can fail, and the loop already handles it — the service should expose it rather than hide it:

- a layer that fails every attempt **falls back to the host's own layer**, and the response says so;
- the composite check can reject an assembled scene that passed layer-by-layer (a pale ground under dense mist rendered
  near-white while every layer passed alone), which triggers regeneration of the likely culprits;
- the herd specialist is the weakest (≈38%), so the cold path should expect to fall back there most often.

A response that says "5 of 6 layers are model-written, the herd is the reference implementation" is more useful than one
that quietly ships a fallback.

---

## What it takes to generate a genuinely new world

This is the end goal, and it is a bigger change than adding an endpoint. Three things are hand-written today:

**1. The host.** `manifest.json`, `scene.js` (the state machine and the per-state values published to layers),
`prelude.glsl.js`, `presets.js`, `camera.js`. Generating these means a *host contract* — the same trick one level up:
state what a host must expose, let a strong model write one, and verify it with the generic gates.

The encouraging part: **the gates are already scene-agnostic.** A second host written independently rendered at gate 1.0
with no harness changes at all. Parses / runs / renders / animates / states transfer to any world.

**2. The segment decomposition.** A canyon has no herd; it may want rockfall and dust. Today the six segments are a fixed
list. A new world needs the director to decide *what layers this world has* before anything can write them — a planning
step above the current planner.

**3. The checks — and this is the real blocker.** Every segment check is calibrated against the host's hand-built layer:
the reference must pass with margin, which is how we know the threshold is honest. A new world has no reference.

Two ways through, and they are both worth testing:

- **Presence checks are already reference-free.** They compare the render against *the host with that layer removed* —
  which needs no hand-built version of the layer, only the host. What needed the reference was choosing the threshold.
  A relative rule ("the layer must change the frame more than the empty case by a clear margin") may calibrate itself.
- **Bootstrap the reference.** Let the strongest available model write the first layer set for the new world, gate it on
  the generic gates plus one human glance, and promote what passes to *be* the reference. Everything downstream — check
  calibration, critique-and-revise, specialist training — then proceeds normally.

The second is how this project would actually grow: a new world costs one careful contract, one bootstrap pass, and one
human look. After that the loop runs unattended.

**What would still be missing.** Even with all three, the specialists are trained per host. A model that writes highpark
grass is not a model that writes canyon scree. Either each world gets its own specialists (linear cost per world), or
specialists are trained across many worlds so the contract — not the world — is what they learn. The second is the more
interesting research direction and nothing here tests it yet.
