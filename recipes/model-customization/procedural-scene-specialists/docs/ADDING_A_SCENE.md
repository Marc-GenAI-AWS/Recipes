# Adding a new scene

The pipeline is not tied to the example worlds. Pointing it at a new one — a canyon, a harbour, a city street — means
writing a **contract** the models code against and a **check** that proves the result is really there. Everything else
(generation, critique-and-revise, training, evaluation, the director) works unchanged.

This walkthrough is the real one: the `ocean` segment on the `seastate` host was added exactly this way, and the mistakes
below are the mistakes that were actually made, in the order they surfaced.

---

## Where new files live

Adding a **segment to an existing host** touches three files and creates one directory of data:

```
pipeline/contract/<segment>_contract.py     the prompt the model codes against          NEW
pipeline/contract/<segment>_briefs.py       the seeded brief sampler                    NEW
pipeline/contract/segments.py               one entry registering the above             edit
pipeline/harness/checks.py                  the segment's presence/quality check         edit
data/<segment>_<tag>/                        generated layers + log.jsonl                created by a run
```

Adding a **whole new host scene** adds one more directory:

```
golden-scenes/<host>/
├── manifest.json        name, title, states, build file list
├── scene.js             the state machine and per-state values published on ctx.cur
├── prelude.glsl.js      shared GLSL helpers your layers may call
├── presets.js           the per-state palette
├── camera.js            the viewpoint layers are judged from
└── layers/*.js          the hand-built reference layers — including the one you are replacing
```

The host must already render on its own. That reference implementation is not optional: it is what the verifier compares
against, and what tells you a threshold is calibrated rather than guessed.

---

## The steps

### 1. Prove the harness can render the host untouched

Before writing anything, check the host renders and passes the generic gates:

```bash
python scripts/render_host.py <host>          # expect gate 1.0
```

If this fails, fix the host first. The gates (parses / runs / renders / animates / states) are scene-agnostic; a new host
usually needs no harness changes at all.

### 2. Write the brief sampler

Copy an existing `*_briefs.py`. A brief conditions the *character* of the layer, never the per-state palette — that comes
from the host. Keep it seeded: **seed 1 is the held-out evaluation set** and must never be used for training data.

### 3. Write the contract

Copy an existing `*_contract.py` and state the whole API surface the layer may use. Two rules earned the hard way:

- **Prose, never example code.** A `vec2 dir = ...` example in one contract was copied verbatim into 47 generated layers,
  including into places where a `vec3` was required. If you show code, you will get that code back.
- **State the preconditions the reference layer satisfies silently.** This is where new scenes actually fail — see below.

### 4. Write and *calibrate* the check

The generic gates only prove the layer ran. The segment check proves the thing the brief asked for is actually on screen.
Write it, then **calibrate it against the host's own hand-built layer**:

```bash
python scripts/calibrate_check.py <host> <layer> <check>
```

The reference layer must pass with margin. If your threshold sits just under it, it is a coin toss, not a check:

| Check | Reference layer scores | Threshold | Verdict |
|---|---|---|---|
| `water_presence` | 43–45 | 8 | comfortable |
| `herd_presence` | 1.13–3.8 | 1.0 | knife-edge — caused months of false failures |

### 5. Audit the contract against the source *before* spending on GPUs

```bash
python scripts/verify_contract.py <segment>
```

This compares every GLSL signature named in the contract against the host's actual prelude, and reports helpers the
contract forgot to mention. It exists because the first ocean run scored **0/12 on two contract bugs**: a required
`#define` that was never mentioned, and two helpers documented as taking a `vec3` when they take a `vec2`. The model
followed the specification it was given. That run cost real money to learn nothing.

### 6. Probe small, bucket the failures, iterate

Run 12 briefs, not 96:

```bash
./run_segment.sh <segment> --n 12 --tag probe
python scripts/failure_classes.py data/<segment>_probe
```

Then fix **one class per round** and re-run the same briefs. Judge by the failure-class table, not the pass rate — the
rate can stay flat while the errors underneath change completely:

| Failure class | v1 | v2 | v3 |
|---|---|---|---|
| GLSL swizzle | 1 | 0 | 0 |
| JS runtime | 2 | 5 | 0 |
| GLSL other | 1 | 0 | 4 |
| **pass** | **5/12** | **3/12** | **3/12** |

Every rule added worked on its target class, and the total never moved. A pass-rate-only reading would have concluded
"prompt tuning does not help", which is the wrong lesson.

### 7. Know when to stop

Stop iterating the contract when a failure class survives two rounds. At that point the errors are no longer missing
knowledge — they are consistency slips inside a long file, which is what fine-tuning fixes and prose does not. For the
ocean segment that plateau was ~3–5 of 12; the remaining route is teacher data and a specialist, not more wording.

---

## The trap that costs the most: contracts are tuned to their incumbent model

A contract that has been iterated against one model quietly encodes conventions that model already knows. Point a
*different* model at it and those unstated assumptions surface all at once.

The mature `ground` contract described its vertex-shader helper as "providing `varying vec3 vP, vN;`". Every model
trained on its data already knew the fragment shader must re-declare those varyings — so the contract never said it. A
fresh model read the contract literally:

| | Pass rate on the same 24 briefs |
|---|---|
| Before the one-line fix | **0 / 8** |
| After | **18 / 24** |

So when you bring a new teacher model to an existing contract, **audit the contract first**. Budget an hour per segment
for it; it is far cheaper than concluding the model is weak.

---

## Cost, so you can plan

Measured on `ml.g6.24xlarge` with a 27B teacher at `--workers 4 --max-num-seqs 4`:

| Step | Cost |
|---|---|
| Probe, 12 briefs | ~$2 |
| Teacher data, 96 briefs | ~$17, ≈70 usable layers |
| Fine-tune one 8B LoRA | ~$7 |
| Held-out evaluation, 24 briefs | ~$4 |

Throughput matters more than it looks: the same work at `--workers 2 --max-num-seqs 2` cost roughly four times as much
per usable layer. Check your concurrency before concluding anything about price.
