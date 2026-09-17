# Procedural Scene Specialists

**Fine-tune small per-layer specialist models to write real-time 3D scene code, and let a render harness — not a human and not an LLM judge — decide what ships.**

A scene is split into layers (sky, ground, vegetation, fauna, effects, camera). Each layer gets its own
small LoRA. Every generated layer is swapped into an otherwise-frozen host scene, rendered headless, and
scored against objective gates. Anything that does not render is not training data.

## Use this when

- You want **small, cheap models** to do a narrow generative task well, rather than paying frontier prices
  per call. Five of the six specialists here are Qwen3-8B LoRAs.
- Your output is **executable or renderable**, so correctness can be *measured* instead of judged. Code,
  shaders, scene graphs, configs, SQL — anything you can run.
- You need **training data you can trust**. The verifier is the filter: a layer enters the dataset only if
  it parses, runs, renders, animates and responds to state changes.
- **When NOT to use this:** if quality is purely subjective and you have no programmatic check, the central
  idea here does not transfer. An LLM judge was tried on this task and produced almost no signal
  (match 1.43 vs mismatch 1.36) on anything except whole-frame properties.

## Results / validation

Six specialists, scored on 24 held-out briefs each, against the teacher that generated their training data:

| Segment | Specialist | Teacher | Notes |
|---|---|---|---|
| Effects | 95.8% | 96% | matches the teacher |
| Camera | 92% | 75% | **beats** the teacher |
| Ground | 87.5% | 79% | **beats** the teacher |
| Sky | 87.5% | 92% | |
| Vegetation | 70.8% | 79% | |
| Fauna | 37.5% | 100% | weakest; compact moving subjects are hard |

Data generation cost, frontier teacher vs a self-hosted 27B:

| Generator | Usable rows | Cost per usable row |
|---|---|---|
| Frontier API teacher | 19/24 | $0.79 |
| Self-hosted Qwen3.8-27B | 18/24 | **$0.23** |

The 27B is ~3.4x cheaper per accepted layer at near-parity quality, and removes the API dependency.

**The gates are scene-agnostic.** Seven hosts of very different character — a prairie basin, a flooded
sinkhole, open ocean, a slot canyon, an alpine glacier, a rain-wet city street, a volcanic caldera — all
render at gate 1.0 with no harness changes.

## What is actually in here

```
golden-scenes/       seven complete host scenes + the shared runtime contract
  <host>/
    manifest.json      states, build file list, the ground-height field contract
    scene.js           state machine; publishes per-state values on ctx.cur
    prelude.glsl.js    shared GLSL: helpers, base shaders, tonemap tail
    field.js           CPU height field (mirrors the GLSL so geometry agrees)
    materials.js       material factories built by string-surgery on the bases
    camera.js          the viewpoint every layer is judged from
    layers/*.js        hand-built reference layers - the calibration baseline
pipeline/
  contract/descriptor.py   derives the contract from host SOURCE (see below)
  harness/                 assemble -> render -> gate -> per-segment checks
  training/                SFT and RL entrypoints
  sagemaker/               container build + job launcher
docs/ADDING_A_SCENE.md     how to add a segment or a whole new world
docs/SERVICE.md            turning the loop into a request/response service
scripts/                   render_host, calibrate_check, verify_contract, ...
```

## The idea worth stealing: derive the contract, don't write it

Every contract bug in this project was a hand-written description drifting from the code it described — a
required `#define` never mentioned, helpers documented as taking a `vec3` that take a `vec2`, a varying the
fragment shader had to re-declare. All were invisible to models trained on that host (they had learned the
convention from data) and fatal to a fresh model reading the contract literally.

So the host half of the prompt is **extracted from source**, not written:

```python
from pipeline.contract.descriptor import contract_text
prompt = contract_text("canyon", "Scrub", intent="desert brush clinging to the wall feet")
```

`descriptor.py` reads the host and emits: GLSL helper signatures, which prelude exports are complete
shaders vs. snippets vs. epilogues, uniform names *with their GLSL types*, which `ctx.cur` fields are
scalars vs. 3-component values, required `#define`s, and the world's scale in world units. A new world
costs an extraction plus a paragraph of intent, and the description cannot drift from the source because
it is generated from it.

## A note on model licensing

The results above were produced with `Qwen/Qwen3.8-27B`, which carries no additional
use restrictions. During development we also evaluated `ukisai/Swift-Qwen3.8-27b`, a
reasoning-efficiency finetune of the same base, and found it wrote better code on this
task in a small sample.

**That model's licence permits personal and research use only — commercial use requires a
separate licence from its authors.** If you are evaluating this recipe for commercial work,
use the base `Qwen/Qwen3.8-27B`, which is what every number in this README was measured on.
The pipeline speaks OpenAI-compatible chat completions, so swapping the generator is a
change of endpoint and model name, nothing more.

Check the licence of any model you substitute in. The verifier does not care which model
wrote a layer, which is the point — but your legal team will.

## Prerequisites

- Python 3.11+, Node 18+
- Chromium for headless rendering (Playwright); CPU-only is fine
- For training: an AWS account with SageMaker access, or any single 24 GB+ GPU
- For generation: an API-based teacher model, **or** a self-hosted server (vLLM) — the pipeline speaks
  OpenAI-compatible chat completions either way

## Environment variables

```bash
export AWS_REGION=us-west-2
export S3_BUCKET=your-bucket                        # training data + artifacts
# choose ONE generator:
export TEACHER_ENDPOINT=http://your-vllm:8001/v1    # self-hosted
export TEACHER_MODEL=qwen3-27b
```

See `.env.example` for the full list.

## Run it

```bash
pip install -r requirements.txt
./scripts/fetch_vendor.sh                    # vendored three.js, for offline renders

# 1. prove the harness can render a host untouched - do this first, always
python scripts/render_host.py canyon           # expect: gate 1.0
python scripts/render_host.py canyon --shots /tmp/canyon   # and look at the frames

# 2. audit a segment's contract against the host it codes against
python scripts/verify_contract.py vegetation   # takes a SEGMENT; --all to sweep every one

# 3. generate + verify layers for one segment (teacher writes, harness decides)
python -m pipeline.teacher --segment vegetation --n 24 --seed 2 --tag train
#    seed 1 is the held-out evaluation set - never generate training data with it

# 4. build an SFT set from what passed, then train
python -m pipeline.build_sft --segment vegetation
python -m pipeline.sagemaker.launch_job sft --segment vegetation

# 5. assemble a whole scene from plans (all six segments, then composite checks)
python -m pipeline.planner --themes 4 --out plans.json
python -m pipeline.director --plans plans.json --out runs/scene-001 \
    --endpoint vegetation=http://your-vllm:8001/v1
```

Expected output / next steps:

- `render_host.py` prints `gate 1.0 {'parses': True, 'runs': True, ...}`
- the director writes accepted layers plus a `log.jsonl` of every attempt and why it failed
- assembled scenes are single self-contained HTML files you can open directly in a browser

## Two things that cost us weeks

**Calibrate every check against the host's own layer.** A check is a specification. If the reference layer
only just clears the threshold, the check is a coin toss that rejects good work; if an empty layer passes,
it is not a check at all. Both happened here. `scripts/calibrate_check.py` scores the reference *and* a
do-nothing stub so you can see the margin. Record the numbers in the check's docstring.

**Gate 1.0 does not mean the subject is visible.** A fish layer passed every structural gate while being
effectively invisible — its frame-diff was 0.32/0.35/1.45 against the host's own layer at 1.96/2.44/1.16.
Structural gates prove the code runs, not that anything is *there*. That is what the per-segment presence
checks are for, and why the derived contract states the world's scale in world units.

## Architecture

`docs/SERVICE.md` covers the request/response shape, the three latency tiers, and — honestly — what is
still missing before a genuinely new world can be generated end to end.

## License

MIT (inherits from repo root).
