# Distilling a Coding Agent into Small Specialists — Godot Video Game

**Replace one large model that writes everything with a set of small fine-tuned models
that each write one part — by building a verifier that renders and judges the output, and
using that same verifier to filter the training data, score the models, and gate the
agentic loop.**

A large model writes candidate code, the verifier renders it in the real application and
judges the result, and only what passes becomes training data. Fine-tune one small model
per part, and at run time a director splits a one-line request into a brief per part, each
specialist writes its own code, and the verifier decides what ships. The worked example is
a Godot 4 game: five specialists write the sky, terrain, water, planting and street
furniture of a playable scene from a single sentence.

**Live output:** [marc-genai-aws.github.io/godot-game/specialist-scenes](https://marc-genai-aws.github.io/godot-game/specialist-scenes/)
— playable scenes with the code written by 3B and 7B models.

## Use this when

- **Your domain has a machine-checkable definition of "good".** Code that compiles and
  runs, a scene that renders, a config that deploys, a query that returns the right rows.
  If a program can render or execute the output, this recipe applies; the rendering is
  what makes small models trainable without armies of human labellers.
- **You want to cut inference cost or bring generation on-prem**, and a frontier model per
  request is the thing you're replacing. Each specialist here is a 3B or 7B LoRA that runs
  on one GPU.
- **One big prompt is doing too many jobs at once.** Splitting by part gives each model a
  narrow contract, a narrow vocabulary, and its own pass rate you can watch move.
- **You already have a working reference implementation** — the hand-built version the
  models learn to match, and the thing the verifier compares against.
- **Not this recipe:** subjective output with no automatable check (marketing copy, chat
  tone), or a domain where you cannot execute the model's output safely. The verifier is
  the whole trick; without one, you are back to human labelling.

## Results / validation

Five specialists, each a LoRA fine-tune of Qwen2.5-Coder, measured on held-out briefs by
the same verifier that filtered their training data. "Teacher" is Claude Sonnet writing
the same briefs, scored identically.

| Segment | Base | One-shot | After one self-revision | Teacher, same briefs |
|---|---|---|---|---|
| Sky | 3B | **80%** | **90%** | 73% |
| Props (street furniture) | 7B | **71%** | **95%** | 52% |
| Vegetation | 3B | **72%** | **83%** | 57% |
| Water | 3B | 46% | **63%** | 42% |
| Ground (terrain) | 3B | 32% | **68%** | 34% |

Every specialist beats the model that taught it, after one revision round. The director —
the model that turns one sentence into per-part briefs — was distilled the same way into a
local 8B and scores 47/47 on held-out scene briefs against the teacher's 80% first pass.

| Cost / time | Value |
|---|---|
| Data generation, one part | ~$25 of Bedrock for ~290 usable examples |
| Fine-tune, 3B LoRA | ~50 min on one `ml.g6e.xlarge` |
| Fine-tune, 7B LoRA | ~1 h 45 on one `ml.g6e.xlarge` |
| Inference | 3B ≈ 7 GB, 7B ≈ 15 GB of GPU memory, local |

### Four findings worth stealing

1. **Your training sequence length silently caps quality.** Every job here ran at a 6,144
   token cut-off, which the two largest parts exceeded: 528 of 529 props examples were
   truncated, so every repair example lost its entire answer. Raising the cut-off took
   props from 38% to 71% one-shot with *no data change*. Measure the token length of your
   examples before you tune anything else — `scripts/check_lengths.py`.
2. **A judge's pass bar is a product decision, not a technical one.** Ask a human to label
   ~24 outputs and compare against candidate bars (`pipeline/anchor.py`). One bar change on
   sky moved its usable training data from 109 examples to 718 and its pass rate from 13%
   to 80%. Most of that was the bar, not the model — which you only know because the
   labels exist.
3. **Never change judges mid-project without re-scoring.** Swapping judge models made one
   part look like it had collapsed overnight (77% → 13%) when the model was identical. Keep
   the raw verdicts so you can re-score old results for free.
4. **Deterministic checks catch what a judge rambles about.** Cheap static checks — does it
   compile, are the API names real, is the draw-call budget met — fail fast with an exact
   message. A model that was told "Function `cosf()` not found" burned five revision rounds;
   told "`cosf()` is C, not GDScript; use `cos()`" it fixed it immediately.

## How it works

Two loops share one verifier.

**Making a specialist** (once per part):

```
briefs  ->  teacher writes N candidates  ->  verifier renders + judges
                                                     |
                              only what passes  ->  SFT dataset  ->  LoRA fine-tune
```

**Making an artifact** (every request):

```
one line  ->  director  ->  a brief per part  ->  specialists write code
                                                          |
                                     verifier renders, captures, judges
                                       |  fail: evidence -> revise (up to N rounds)
                                       v
                             composite check on the assembled result
                                       |  blame -> back to that specialist
                                       v
                                 accepted output ships
```

The verifier is four stages, cheapest first, so most failures cost nothing:

| Stage | What it does | Cost |
|---|---|---|
| Static gate | Parses the code, checks API names and arities against the engine's own class database | free |
| Runtime gate | Loads it in the real application headless, fails on any script error | free |
| Checks | Deterministic, domain-specific: sun angle vs the brief, palette moved, draw-call budget, frame rate | free |
| Judge | A vision model scores rendered captures against the brief and a rubric | ~$0.03 |

## Prerequisites

- AWS account with **Amazon Bedrock** access to a strong model (teacher and judge) and
  **SageMaker AI** training quota for `ml.g6e.xlarge` or similar
- IAM: a SageMaker execution role with read/write on your bucket; Bedrock `InvokeModel`
- A **GPU machine with a display** for the captures (the verifier renders the real
  application; headless-without-GPU will not work)
- [Godot 4.7+](https://godotengine.org/download) and the example game:
  `git clone https://github.com/Marc-GenAI-AWS/godot-game`
- Python 3.11+

## Environment variables

```bash
export AWS_REGION=us-west-2
export SAGEMAKER_BUCKET=sagemaker-us-west-2-123456789012
export SAGEMAKER_ROLE=arn:aws:iam::123456789012:role/service-role/AmazonSageMaker-ExecutionRole-...
export GAME_DIR=/path/to/godot-game/game
export GODOT_BIN=/path/to/Godot_v4.7-stable_linux.x86_64
export DISPLAY=:0            # the captures need a real display
```

Everything else lives in [`pipeline/config.py`](pipeline/config.py), marked `CUSTOMER SETUP`.

## Run it

```bash
pip install -r requirements.txt

# 1. sample briefs for one part (here: the sky)
python pipeline/briefs.py sky --n 144 --seed 1 --out runs/sky1/briefs.jsonl

# 2. teacher writes two candidates per brief, the verifier renders and judges each,
#    failures get one revision, and survivors become the dataset  (~$25, a few hours)
./run_segment.sh sky sky1 144 2

# 3. check your examples fit the training sequence length BEFORE you train
python scripts/check_lengths.py runs/sky1/sft/train.jsonl --max-len 14336

# 4. fine-tune on SageMaker, then evaluate on the held-out briefs
./train_eval_segment.sh sky sky1

# 5. generate something with it
python pipeline/loop/director.py "a clear tropical noon on the beach, golden sand" \
    --out runs/scene1 --segments sky,ground,vegetation,props \
    --backend sky=hf:/path/to/sky-model,ground=hf:/path/to/ground-model \
    --rounds 3 --composite
```

### Calibrating the judge (do this early)

```bash
# build a page of ~24 outputs spanning the judge's scores, label them by hand,
# then see which pass bar agrees with you
python pipeline/anchor.py build --run sky1 --out runs/anchor1
python pipeline/anchor.py score --labels "anchor1 S01P S02F ..." --key runs/anchor1/key.json
```

The output tells you how often each candidate bar agrees with a human, and what each bar
would do to your dataset size. Set the bar in `SEGMENTS[...]["pass_bar"]` in
[`pipeline/common.py`](pipeline/common.py).

## What's in here

| Path | What it is |
|---|---|
| `pipeline/config.py` | Every account- and machine-specific value |
| `pipeline/briefs.py` | Brief sampler — covers the space evenly rather than randomly |
| `pipeline/teacher.py` | Teacher generation and revision through Bedrock |
| `pipeline/verify.py` | **The verifier**: gates, captures, checks, judge, composite |
| `pipeline/gdcheck.py` | Static checks against the engine's class database |
| `pipeline/build_sft.py` | Verified rows to an SFT dataset, with a pinned held-out split |
| `pipeline/anchor.py` | Build and score a human anchor set to set the judge's bar |
| `pipeline/loop/director.py` | The agentic loop: plan, write, verify, revise, composite |
| `pipeline/loop/specialist.py` | Specialist inference — local, an OpenAI-compatible server, or a SageMaker endpoint |
| `pipeline/sagemaker/` | LoRA training job (`train_sft.py`) and its launcher |
| `pipeline/contract/`, `pipeline/rubrics/` | Per-part contracts (the system prompt) and judge rubrics |
| `scripts/check_lengths.py` | Token-length audit of a dataset — run before every training job |

## Adapting it to your domain

The parts to replace, in order of effort:

1. **`pipeline/contract/<part>.md`** — the system prompt: what this part may touch, the
   API it may call, what "good" means. This is the biggest lever on output quality.
2. **`CHECKS` in `pipeline/verify.py`** — your deterministic checks. Anything you can
   measure without a model belongs here; it is free and it never drifts.
3. **`capture()` in `pipeline/verify.py`** — how you exercise the artifact. Here it drives
   the game and screenshots it; yours might hit an endpoint, run a test suite, or diff a
   rendering.
4. **`pipeline/rubrics/<part>.md`** — what the judge weighs, and what it should ignore.
5. **`pipeline/briefs.py`** — the space of requests worth covering.

Everything else — the data loop, the training job, the anchor tooling, the agentic loop —
is domain-independent.
