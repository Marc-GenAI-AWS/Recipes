# WAN 2.2 on a SageMaker Async Inference Endpoint

Reference implementation of a SageMaker managed inference endpoint that serves the
WAN 2.2 TI2V-5B text-to-video model with runtime LoRA swapping, using the
AWS-managed PyTorch DLC and stock Diffusers APIs.

## What this shows

- The base model loads once at container start (~24 GB resident on GPU).
- Each request may name an `adapter_s3_uri`. The container downloads the LoRA (if
  not already cached), applies it with stock `load_lora_weights()`, and generates a
  video. Adapters are cached across requests, and `adapter_scale` dials strength.
- Adding a LoRA does **not** require redeploying — the base model stays warm.
- The container is the AWS-managed PyTorch inference DLC. No custom Docker image.
- No custom model or LoRA conversion code. Diffusers handles both natively.

## Design constraint worth understanding up front

SageMaker has a managed multi-adapter feature: adapter `InferenceComponent`s attached
to a base component, selected per-request via `InferenceComponentName`. **It does not
work for diffusion models.** It is implemented on top of vLLM's multi-LoRA support
inside the LMI container (requires `0.31.0-lmi13.0.0`+, tuned with
`OPTION_MAX_LORAS` / `OPTION_MAX_CPU_LORAS`) and is text-LLM only.

Pointing a base inference component at the PyTorch DLC would not help: the container
receives the `InferenceComponentName` header but has no idea how to apply an adapter,
so you would write the loading logic yourself regardless.

So this project implements the **diffusion equivalent**: adapters addressed by S3 URI
at request time, cached in the container. If AWS extends managed adapters to
diffusion, the S3 artifact layout here carries over and migration is mostly swapping
the container image and registering each adapter as an InferenceComponent.

## Why async instead of response streaming

Generation runs for minutes and produces a large binary artifact — exactly what
async inference is for. It also avoids custom container code: the stock
`sagemaker-pytorch-inference-toolkit` does **not** stream a generator returned from
`predict_fn`, so real streaming would mean hand-writing TorchServe
`send_intermediate_predict_response` calls.

| | Real-time streaming | Async (this project) |
|---|---|---|
| Custom container code | Required | None |
| Invocation cap | 60 s | 60 min |
| Request queueing | You build it | Managed |
| Scale to zero | No | Yes |
| Live progress events | Yes | No — completion only |

The tradeoff is losing per-step progress events.

## Layout

```
async/
├── code/                            Syncs to the model prefix, mounts at /opt/ml/model/code/
│   ├── inference.py                 model_fn / input_fn / predict_fn / output_fn
│   ├── lora_cache.py                On-demand S3 -> local LoRA cache
│   └── requirements.txt             Fully pinned
│
└── deploy/
    ├── config.py                    Region, S3 URIs, role ARN, instance type, image
    ├── deploy.py                    One-command launch (idempotent)
    ├── teardown.py                  One-command shutdown -- stops the billing
    ├── preflight.py                 Validate S3 artifacts before deploying
    ├── 04_invoke.py                 Submits a generation, polls for the result
    │
    ├── 01_create_model.py           } orchestrated by deploy.py,
    ├── 02_create_endpoint_config.py }   still runnable individually
    ├── 03_create_endpoint.py        }
    └── 05_update_endpoint.py        Blue/green swap to a new Model + config
```

## TL;DR

```bash
cd deploy
python deploy.py                                  # up   (~10 min)
python 04_invoke.py "a prompt" --frames 25 --steps 10
python teardown.py                                # down (stops billing)
```

## S3 layout

```
s3://amzn-s3-demo-bucket/
├── wan2.2-ti2v-5b-diffusers/   Base model, Diffusers format (mounts at /opt/ml/model)
│   └── code/                   Handler code, synced by 01_create_model.py
├── loras/
│   ├── hstoric-color/          Autochrome colour-grade style (rank 64)
│   └── crush-it/               Hydraulic-press motion effect (rank 32)
├── async/{input,output,errors}/ Async request payloads and results
└── generations/                Output MP4s
```

### The base model must be in Diffusers format

`WanPipeline.from_pretrained()` needs `model_index.json` plus `transformer/`, `vae/`,
`text_encoder/`, `tokenizer/`, `scheduler/`. The original `Wan-AI/Wan2.2-TI2V-5B`
research repo (`Wan2.2_VAE.pth`, `models_t5_umt5-xxl-enc-bf16.pth`, a `config.json`
with `_class_name: WanModel`) does **not** load — it fails with
`OSError: Error no file named model_index.json`.

Use `Wan-AI/Wan2.2-TI2V-5B-Diffusers`.

## LoRA compatibility — the part that bites

A WAN LoRA must satisfy two things:

**1. It must target the 5B model.** Most WAN 2.2 LoRAs are trained against the 14B
models (`T2V-A14B` / `I2V-A14B`), which have a different architecture. They will not
load onto TI2V-5B.

**2. Its keys must be a format Diffusers recognises.** Three formats exist in the wild:

| Key style | Example | Works with `load_lora_weights()`? |
|---|---|---|
| Diffusers-native | `transformer.blocks.0.attn1.to_k.lora_A.weight` | Yes, directly |
| ComfyUI / ai-toolkit | `diffusion_model.blocks.0.cross_attn.k.lora_A.weight` | Yes — auto-converted |
| Raw PEFT, unprefixed | `blocks.0.cross_attn.k.lora_A.default.weight` | No |
| PEFT-wrapped Diffusers | `base_model.model.blocks.0.attn1.to_k.lora_A.weight` | No — `WanLoraLoaderMixin` only tests for the `diffusion_model.` prefix |

In practice the second row is what you will meet: every Apache-2.0 5B adapter surveyed
for this project was ai-toolkit/ComfyUI output. Check the keys before assuming, though
— a LoRA in an unsupported format fails by loading *nothing*, not by raising.

Diffusers detects the `diffusion_model.` prefix and runs
`_convert_non_diffusers_wan_lora_to_diffusers`, mapping `self_attn.{q,k,v,o}` ->
`attn1.to_{q,k,v}/to_out.0`, `cross_attn.*` -> `attn2.*`, and `ffn.{0,2}` ->
`ffn.net.0.proj`/`ffn.net.2`. It handles both `lora_A`/`lora_B` and
`lora_down`/`lora_up` naming.

The bundled LoRA (`AlekseyCalvin/HSToric_Color_Wan2.2_5B_LoRA_BySilverAgePoets`,
Apache-2.0, rank 64) is the ComfyUI style — all 600 tensors convert onto 300 real
transformer modules with nothing left over.

> **Distillation LoRAs need more than a weight swap.** A 4-step DMD/CausVid-style
> adapter also changes the sampling regime (step count, `flow_shift`, guidance). The
> weights alone are not enough — the scheduler must be reconfigured to match, or
> output quality collapses.

## Prereqs

Three fields at the top of `deploy/config.py` must be set for your AWS account
before the first deploy — the block is annotated with a `CUSTOMER SETUP` header:

1. **Region** — all resources (endpoint, S3 bucket, ECR image) must live in the
   same region. If it is not `us-west-2`, also update `INFERENCE_IMAGE_URI`; the
   DLC image URI is region-scoped.
2. **S3 bucket** — a bucket you own, populated as described below.
3. **SageMaker execution role** — must trust `sagemaker.amazonaws.com` and grant
   `AmazonSageMakerFullAccess` (or equivalent), read on `s3://<your-bucket>/*`,
   write on `s3://<your-bucket>/generations/*` and `s3://<your-bucket>/async/*`,
   and CloudWatch Logs write on the endpoint's log group.

Also required: AWS credentials on the machine running `deploy.py`
(`aws sts get-caller-identity` should return the account you expect), and service
quota for `ml.g6e.8xlarge` in the region.

### Populating your bucket

The endpoint reads everything from your bucket. Before the first deploy:

```bash
hf download Wan-AI/Wan2.2-TI2V-5B-Diffusers --local-dir wan2.2-ti2v-5b-diffusers
aws s3 sync wan2.2-ti2v-5b-diffusers s3://amzn-s3-demo-bucket/wan2.2-ti2v-5b-diffusers/
```

Upload at least one LoRA under `loras/<name>/` — the two adapters in the
[Validated adapters](#validated-adapters) table are public Hugging Face repos —
or pass `--no-adapter` to `04_invoke.py`. The `generations/` and `async/` prefixes
are created on first write. `preflight.py` validates the layout and every adapter's
key format before you pay for a deploy.

## Deploy

```bash
cd deploy
python deploy.py        # preflight -> upload code -> create what's missing -> verify
```

Idempotent, so re-running is safe. Takes ~10 min, almost all of it the 34 GB model
download. When it prints `READY` the worker has been confirmed loaded, not merely
reported healthy.

```bash
python teardown.py      # delete the endpoint -- this is what stops the billing
python teardown.py --status
python teardown.py --all   # also delete Model + EndpointConfig
```

`teardown.py` keeps the Model and EndpointConfig by default. They cost nothing to
retain and make the next `deploy.py` a single API call instead of a rebuild. Use
`--all` only when changing the model artifact or container settings — both names are
immutable, so otherwise you would have to bump them in `config.py`.

### Preflight

```bash
python preflight.py     # seconds, no torch, no GPU
```

Validates the S3 artifacts before you pay for a deploy: Diffusers layout, handler
code, pinned requirements (including `ftfy`), and every adapter's key format —
confirming each one's tensors convert onto modules that actually exist in the base
model. Each check corresponds to a failure that otherwise appears only after the
container has downloaded 34 GB, or that never raises at all.

`deploy.py` runs it automatically; `--skip-preflight` opts out.

### Why `deploy.py` does not trust `EndpointStatus`

An endpoint reports **`InService` while its worker is in a crash-restart loop** — this
bit us twice. `EndpointStatus` reflects the container's health check, not whether
`model_fn` succeeded. The reliable signal is `Pipeline ready` in CloudWatch, which is
what `deploy.py` waits for.

It also only reads log streams created *after* the deploy started. The log group
outlives the endpoint, so a stale stream from a previous attempt will otherwise be
read as though it described the current one.

### Step-by-step scripts

`deploy.py` orchestrates `01`–`03`, which remain runnable individually. To change the
model artifact or container config, bump the names in `config.py` and run
`05_update_endpoint.py` for a blue/green swap.

## Invoke

```bash
python 04_invoke.py "A steam train crossing a bridge, HST style HD film, early 1900s, autochrome"
python 04_invoke.py "..." --no-adapter              # bare base model
python 04_invoke.py "..." --adapter-scale 0.6       # dial LoRA strength
python 04_invoke.py "..." --adapter s3://amzn-s3-demo-bucket/loras/some-other-lora/
```

The default adapter (`hstoric-color`) is a style LoRA trained on early-1900s autochrome photography;
its trigger phrase is `HST style HD film, early 1900s, autochrome, analog cinema`.
Running the same prompt and seed with and without `--no-adapter` is the clearest way
to show the adapter doing real work.

Result:

```json
{
  "request_id": "...",
  "video_s3_uri": "s3://amzn-s3-demo-bucket/generations/....mp4",
  "adapter_s3_uri": "s3://amzn-s3-demo-bucket/loras/hstoric-color/",
  "adapter_scale": 1.0,
  "timings": {"adapter_s": 3.1, "denoise_s": 214.7, "encode_upload_s": 2.4}
}
```

## Measured performance

On `ml.g6e.8xlarge` (1x L40S), 1280x704, 25 frames, 10 steps:

| Phase | Cold adapter | Warm adapter | No adapter |
|---|---|---|---|
| Adapter load | 1.92 s | 0.42 s | 0.02 s (unload) |
| Denoise | 29.08 s | 28.94 s | 26.82 s |
| Encode + upload | 0.56 s | 0.56 s | 0.61 s |
| **Total** | **~35 s** | **~30 s** | **~28 s** |

Denoising runs at ~1.5 s/step at this resolution and frame count. The pipeline
defaults (49 frames, 30 steps) are correspondingly heavier — budget several minutes
per request; the numbers above are measured, that one is extrapolated.

Swapping between two adapters on one warm instance (`A -> B -> A`):

| Step | Adapter load | Note |
|---|---|---|
| A (warm) | 0.41 s | already on disk |
| A -> B | 1.38 s | B downloaded from S3 on first use |
| B -> A | 0.43 s | no re-download; both stay cached |

Only the GPU-side unload/apply repeats on a swap — the S3 fetch happens once per
adapter per instance lifetime.

## Validated adapters

Both are public Hugging Face repos — download and upload to your bucket under
the prefixes shown (or any prefix; the URI is passed per request).

| Prefix | Source | License | Rank | Trigger |
|---|---|---|---|---|
| `loras/hstoric-color/` | `AlekseyCalvin/HSToric_Color_Wan2.2_5B_LoRA_BySilverAgePoets` | Apache-2.0 | 64 | `HST style HD film, early 1900s, autochrome` |
| `loras/crush-it/` | `ostris/wan22_5b_i2v_crush_it_lora` | Apache-2.0 | 32 | `crush it` |

Differing ranks (64 and 32) load through the same code path — rank is read from the
adapter, not configured.

Note that `crush-it` was trained for image-to-video. It still loads and influences
text-to-video output (TI2V-5B shares one transformer across both tasks), but being a
*motion* effect it reads better in the full clip than in a single frame.

## Adding your own LoRA

Drop it at any S3 prefix and pass that URI as `adapter_s3_uri`. No redeploy:

```bash
aws s3 cp my-lora.safetensors s3://amzn-s3-demo-bucket/loras/my-style/
python 04_invoke.py "..." --adapter s3://amzn-s3-demo-bucket/loras/my-style/
```

`adapter_s3_uri` accepts a prefix (first `*.safetensors` wins, `adapter_model*`
preferred) or a direct URI to a single `.safetensors` file.

## Limits and knobs worth knowing

- **Async invocation cap:** 60 min (`InvocationTimeoutSeconds`).
- **Container-side timeout:** `TS_DEFAULT_RESPONSE_TIMEOUT=3600`. TorchServe enforces
  this independently of the SageMaker limit — the original 480s value silently killed
  the worker mid-generation.
- **Worker count:** `SAGEMAKER_MODEL_SERVER_WORKERS=1`. TorchServe otherwise spawns one
  worker per GPU, each loading its own ~24 GB copy of the pipeline.
- **Endpoint creation:** ~10 min end to end. Most of that is the 34 GB artifact
  download; the pipeline itself loads to GPU in ~4 s once the files are local.
- **LoRA load:** ~1.9 s cold (S3 download), ~0.4 s warm (local cache), ~0.02 s to
  unload back to base.
- **Frame count** must satisfy `(n - 1) % 4 == 0` — the Wan VAE compresses time 4x.
- **VAE precision:** fp32 while the rest of the pipeline is bf16. This split is
  prescribed by the model card; forcing the VAE to bf16 produces washed-out frames.
- **`flow_shift=5.0`** on `UniPCMultistepScheduler` is the documented setting for 720p
  (3.0 is for 480p). Tunable via the `FLOW_SHIFT` env var.
- **Pipeline defaults** (overridable per request): 1280x704, 49 frames @ 24 fps,
  30 steps, `guidance_scale=5.0`.
- **Memory:** ~24 GB resident of 48 GB on the L40S. If you hit OOM at higher
  resolutions, `enable_model_cpu_offload()` is the next lever before a bigger instance.

## Container image

`pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker-v1.84`

This is the newest PyTorch inference DLC published — 2.6.0 is the highest version
available, and `v1.84` its highest patch tag. Alternatives considered:

- **`huggingface-pytorch-inference`** — its toolkit handles diffusers `text-to-image`
  but not text-to-video, and has no per-request LoRA swap. You would override it with
  a custom handler anyway and inherit a hard `transformers` pin.
- **`djl-inference` / LMI** — text-LLM only.
- **`stabilityai-pytorch-inference`** — diffusion-specific but frozen at torch 2.0.1 /
  py310 / cu118 (last pushed Jan 2024) and built for Stability's SGM, not Diffusers.

`requirements.txt` is fully pinned. Unpinned ranges previously resolved
`transformers` to 5.14.1 — a major version break — inside this image.
