# WAN 2.2 on a SageMaker Real-Time Inference Endpoint

Reference implementation of a SageMaker managed **real-time** inference endpoint that
serves the WAN 2.2 TI2V-5B text-to-video model with runtime LoRA swapping, using the
AWS-managed PyTorch DLC and stock Diffusers APIs.

Sibling to the async project. The container code, LoRA cache, base model artifact,
and adapter format are identical. The difference is on the SageMaker side: no
`AsyncInferenceConfig`, so `invoke_endpoint` returns inline instead of writing to S3.

## Why a real-time endpoint here

Real-time is the natural fit for interactive callers -- a UI, a notebook, a small
service -- that submit a request, wait, and want the result back on the same
connection. No S3 request bucket, no output polling, no failure-record inspection.

The tradeoff is a hard cap.

## The 60-second invocation cap

**SageMaker real-time invocations are hard-capped at 60 seconds.** After that, the
runtime returns `ModelError` / `ReadTimeoutError` regardless of what the container
does -- the generation may still complete inside the worker, but the client has
already given up. This is the ceiling that pushed the original project to async.

### What exactly is capped -- the connection, not the compute

The 60s limit applies to the **response connection**, not to the inference job.
SageMaker's front end holds the caller's HTTPS connection open while the container
works; at 60 seconds it severs that connection and returns HTTP 424 `ModelError`
("Your invocation timed out while waiting for a response from container primary").
The worker is not interrupted -- it keeps generating, and this handler still
encodes and uploads the finished MP4 to S3.

Verified empirically (2026-08): with the client's socket `read_timeout` raised to
600s so the SDK could not be the one giving up, a 49-frame / 30-step request
(~4 minutes of GPU work) was killed by the server at 60.2s -- and the worker
completed the generation regardless.

Two practical consequences:

- **An overrun is the worst of both worlds.** The caller gets an error, yet the
  instance still spends the full generation time -- and the single worker is
  blocked for all of it. Requests that might overrun belong on the async
  endpoint, whose S3-based result delivery has no such cap.
- **The response is lost, not the artifact.** If a timeout slips through, the MP4
  usually still lands at `generations/<request_id>.mp4` -- passing your own
  `request_id` in the payload makes it findable after the fact.

|  | Real-time (this project) | Async (sibling) |
|---|---|---|
| Invocation cap | **60 s** | 60 min |
| Result delivery | Inline, on the same call | Written to S3, poll for it |
| Client code | `invoke_endpoint` | `invoke_endpoint_async` + poll |
| Request queueing | None (429 on overload) | Managed |
| Scale to zero | No | Yes |

If a single generation might exceed 60s, use the async project. This one is for the
short, warm, "generate now" case.

### What actually fits inside 60s

Measured on `ml.g6e.8xlarge` (1x L40S), warm worker, cached adapter:

| Frames | Steps | Denoise | Total end-to-end | Fits 60s? |
|--------|------:|--------:|-----------------:|:---------:|
| 25     |    10 | ~29 s   | ~30 s            | Yes       |
| 25     |    20 | ~58 s   | ~60 s            | Marginal  |
| 49     |    10 | ~57 s   | ~59 s            | Marginal  |
| 49     |    30 | multiple minutes | | No (use async) |

Denoising is ~1.5 s/step at 1280x704, and time scales linearly in both frame count
and step count. The defaults -- injected as container environment variables by
`01_create_model.py` and mirrored by `04_invoke.py` -- are **25 frames / 10 steps**,
the largest measured combination with meaningful headroom.

### Cold-start caveats that eat the budget

- **First adapter fetch** adds ~1.5s over the warm case. Non-fatal at defaults, but
  it shrinks the safety margin.
- **Cold worker after scale-up** is minutes, not seconds. `invoke_endpoint` will
  return an error long before the pipeline finishes loading. Real-time endpoints do
  not scale to zero -- keep at least one instance warm, or accept startup failures.

## What this shows

- The base model loads once at container start (~24 GB resident on GPU).
- Each request may name an `adapter_s3_uri`. The container downloads the LoRA (if
  not already cached), applies it with stock `load_lora_weights()`, and generates a
  video. Adapters are cached across requests, and `adapter_scale` dials strength.
- Adding a LoRA does **not** require redeploying -- the base model stays warm.
- The container is the AWS-managed PyTorch inference DLC. No custom Docker image.
- No custom model or LoRA conversion code. Diffusers handles both natively.

The video artifact is still uploaded to S3 (`s3://amzn-s3-demo-bucket/generations/...`),
and the response carries its URI -- returning the raw MP4 inline would blow past
the 6 MB `invoke_endpoint` response limit for anything past a few frames.

## Layout

```
realtime/
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
    ├── 04_invoke.py                 Blocking invoke_endpoint call, prints the result
    │
    ├── 01_create_model.py           } orchestrated by deploy.py,
    ├── 02_create_endpoint_config.py }   still runnable individually
    ├── 03_create_endpoint.py        }
    └── 05_update_endpoint.py        Blue/green swap to a new Model + config
```

## TL;DR

```bash
cd deploy
python deploy.py                                # up   (~10 min)
python 04_invoke.py "a prompt"                  # defaults: 25 frames, 10 steps
python teardown.py                              # down (stops billing)
```

## S3 layout

```
s3://amzn-s3-demo-bucket/
├── wan2.2-ti2v-5b-diffusers/   Base model, Diffusers format (mounts at /opt/ml/model)
│   └── code/                   Handler code, synced by 01_create_model.py
├── loras/
│   ├── hstoric-color/          Autochrome colour-grade style (rank 64)
│   └── crush-it/               Hydraulic-press motion effect (rank 32)
└── generations/                Output MP4s
```

Note the async-specific prefixes (`async/{input,output,errors}/`) are unused here --
real-time invocation carries the payload and response on the wire.

### Populating your bucket

Set `BUCKET` in `deploy/config.py` to a bucket you own. Every other S3 URI in the
config derives from it. The bucket must exist in the same region as the endpoint --
SageMaker cannot read a model artifact across regions, and the code sync will fail
if the bucket lives elsewhere.

Populate it before deploying:

```
s3://your-bucket/
├── wan2.2-ti2v-5b-diffusers/   Contents of Wan-AI/Wan2.2-TI2V-5B-Diffusers
└── loras/                      At least one adapter prefix, or pass --no-adapter
```

```bash
pip install -U "huggingface_hub[cli]"
hf download Wan-AI/Wan2.2-TI2V-5B-Diffusers --local-dir wan2.2-ti2v-5b-diffusers
aws s3 sync wan2.2-ti2v-5b-diffusers s3://amzn-s3-demo-bucket/wan2.2-ti2v-5b-diffusers/
```

The two adapters in the [Validated adapters](#validated-adapters) table are public
Hugging Face repos:

```bash
hf download AlekseyCalvin/HSToric_Color_Wan2.2_5B_LoRA_BySilverAgePoets --local-dir hstoric-color
aws s3 cp hstoric-color/ s3://amzn-s3-demo-bucket/loras/hstoric-color/ \
    --recursive --exclude "*" --include "*.safetensors"

# optional second adapter (motion effect)
hf download ostris/wan22_5b_i2v_crush_it_lora --local-dir crush-it
aws s3 cp crush-it/ s3://amzn-s3-demo-bucket/loras/crush-it/ \
    --recursive --exclude "*" --include "*.safetensors"
```
 `preflight.py` will fail fast if
either prefix is missing, so you will not pay for a 10-minute deploy against an
empty bucket. The `generations/` prefix is created on
first write by `inference.py` and does not need to exist ahead of time.

### The base model must be in Diffusers format

`WanPipeline.from_pretrained()` needs `model_index.json` plus `transformer/`, `vae/`,
`text_encoder/`, `tokenizer/`, `scheduler/`. The original `Wan-AI/Wan2.2-TI2V-5B`
research repo (`Wan2.2_VAE.pth`, `models_t5_umt5-xxl-enc-bf16.pth`, a `config.json`
with `_class_name: WanModel`) does **not** load -- it fails with
`OSError: Error no file named model_index.json`.

Use `Wan-AI/Wan2.2-TI2V-5B-Diffusers`.

## LoRA compatibility -- the part that bites

A WAN LoRA must satisfy two things:

**1. It must target the 5B model.** Most WAN 2.2 LoRAs are trained against the 14B
models (`T2V-A14B` / `I2V-A14B`), which have a different architecture. They will not
load onto TI2V-5B.

**2. Its keys must be a format Diffusers recognises.** The formats in the wild:

| Key style | Example | Works with `load_lora_weights()`? |
|---|---|---|
| Diffusers-native | `transformer.blocks.0.attn1.to_k.lora_A.weight` | Yes, directly |
| ComfyUI / ai-toolkit | `diffusion_model.blocks.0.cross_attn.k.lora_A.weight` | Yes -- auto-converted |
| Raw PEFT, unprefixed | `blocks.0.cross_attn.k.lora_A.default.weight` | No |
| PEFT-wrapped Diffusers | `base_model.model.blocks.0.attn1.to_k.lora_A.weight` | No -- `WanLoraLoaderMixin` only tests for the `diffusion_model.` prefix |

In practice the second row is what you will meet: every Apache-2.0 5B adapter surveyed
for this project was ai-toolkit/ComfyUI output. Check the keys before assuming, though
-- a LoRA in an unsupported format fails by loading *nothing*, not by raising.

Diffusers detects the `diffusion_model.` prefix and runs
`_convert_non_diffusers_wan_lora_to_diffusers`, mapping `self_attn.{q,k,v,o}` ->
`attn1.to_{q,k,v}/to_out.0`, `cross_attn.*` -> `attn2.*`, and `ffn.{0,2}` ->
`ffn.net.0.proj`/`ffn.net.2`. It handles both `lora_A`/`lora_B` and
`lora_down`/`lora_up` naming.

> **Distillation LoRAs need more than a weight swap.** A 4-step DMD/CausVid-style
> adapter also changes the sampling regime (step count, `flow_shift`, guidance). The
> weights alone are not enough -- the scheduler must be reconfigured to match, or
> output quality collapses.

### Validated adapters

Both are public Hugging Face repos — download and upload to your bucket under
the prefixes shown (or any prefix; the URI is passed per request).

| Prefix | Source | License | Rank | Trigger |
|---|---|---|---|---|
| `loras/hstoric-color/` | `AlekseyCalvin/HSToric_Color_Wan2.2_5B_LoRA_BySilverAgePoets` | Apache-2.0 | 64 | `HST style HD film, early 1900s, autochrome` |
| `loras/crush-it/` | `ostris/wan22_5b_i2v_crush_it_lora` | Apache-2.0 | 32 | `crush it` |

Differing ranks (64 and 32) load through the same code path -- rank is read from the
adapter, not configured. Note that `crush-it` was trained for image-to-video; it
still loads and influences text-to-video output (TI2V-5B shares one transformer
across both tasks), but being a *motion* effect it reads better in the full clip
than in a single frame.

### Adding your own LoRA

Drop it at any S3 prefix and pass that URI as `adapter_s3_uri`. No redeploy:

```bash
aws s3 cp my-lora.safetensors s3://amzn-s3-demo-bucket/loras/my-style/
python 04_invoke.py "..." --adapter s3://amzn-s3-demo-bucket/loras/my-style/
```

`adapter_s3_uri` accepts a prefix (first `*.safetensors` wins, `adapter_model*`
preferred) or a direct URI to a single `.safetensors` file. `preflight.py` validates
every adapter under `loras/` before a deploy, so a key-format problem surfaces in
seconds instead of after the endpoint is up.

## Prereqs

Before the first deploy, three fields at the top of `deploy/config.py` must be set
for your AWS account. The block is annotated with a `CUSTOMER SETUP` header so it
is easy to find.

**1. Region** -- `REGION` in `config.py`. All resources (endpoint, S3 bucket, ECR
image) must live in the same region. Default is `us-west-2`. If you change it,
also update `INFERENCE_IMAGE_URI` -- the DLC image URI is region-scoped (both the
account-ID prefix and the `.us-west-2.` segment change). Look up the matching URI
for your region in AWS's [Deep Learning Containers table](https://github.com/aws/deep-learning-containers/blob/master/available_images.md).

**2. S3 bucket** -- `BUCKET` in `config.py`. See the "Populating your bucket"
section above for the required contents and layout.

**3. SageMaker execution role** -- `ROLE_ARN` in `config.py`. Format is
`arn:aws:iam::<your-account-id>:role/<role-name>`. The role must trust
`sagemaker.amazonaws.com` and grant:

- `AmazonSageMakerFullAccess` (or an equivalent tighter policy)
- `s3:GetObject` on `s3://<your-bucket>/*`
- `s3:PutObject` on `s3://<your-bucket>/generations/*`
- CloudWatch Logs write permission on the endpoint's log group

If you already have a SageMaker execution role in the account, reusing it is
fine -- just paste its ARN.

**Also required, but not in `config.py`:**

- **AWS credentials** on the machine running `deploy.py` -- via `aws configure`,
  an SSO profile, or environment variables. `aws sts get-caller-identity` should
  return the account/role you expect before proceeding.
- **Service quota** for `ml.g6e.8xlarge` in your region. Request it via the AWS
  Service Quotas console under "Amazon SageMaker" if the deploy fails with
  `ResourceLimitExceeded`.

The async output/error paths are not needed for this project.

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
`--all` only when changing the model artifact or container settings -- both names
are immutable, so otherwise you would have to bump them in `config.py`.

### Preflight

```bash
python preflight.py     # seconds, no torch, no GPU
```

Validates the S3 artifacts before you pay for a deploy: Diffusers layout, handler
code, pinned requirements (including `ftfy`), and every adapter's key format --
confirming each one's tensors convert onto modules that actually exist in the base
model. Same checks as the async sibling.

`deploy.py` runs it automatically; `--skip-preflight` opts out.

### Why `deploy.py` does not trust `EndpointStatus`

An endpoint reports **`InService` while its worker is in a crash-restart loop** --
this is a known SageMaker footgun. `EndpointStatus` reflects the container's health
check, not whether `model_fn` succeeded. The reliable signal is `Pipeline ready` in
CloudWatch, which is what `deploy.py` waits for.

It also only reads log streams created *after* the deploy started. The log group
outlives the endpoint, so a stale stream from a previous attempt will otherwise be
read as though it described the current one.

## Invoke

```bash
python 04_invoke.py "A steam train crossing a bridge, HST style HD film, early 1900s, autochrome"
python 04_invoke.py "..." --no-adapter              # bare base model
python 04_invoke.py "..." --adapter-scale 0.6       # dial LoRA strength
python 04_invoke.py "..." --adapter s3://amzn-s3-demo-bucket/loras/some-other-lora/
python 04_invoke.py "..." --frames 25 --steps 10    # explicit (these are the defaults)
```

The default adapter is a style LoRA trained on early-1900s autochrome photography;
its trigger phrase is `HST style HD film, early 1900s, autochrome, analog cinema`.
Running the same prompt and seed with and without `--no-adapter` is the clearest way
to show the adapter doing real work.

If the invocation times out at ~60s with a `ReadTimeoutError`, the request is too
large for real-time. Cut `--frames` or `--steps`, or use the async project.

Result:

```json
{
  "request_id": "...",
  "video_s3_uri": "s3://amzn-s3-demo-bucket/generations/....mp4",
  "adapter_s3_uri": "s3://amzn-s3-demo-bucket/loras/hstoric-color/",
  "adapter_scale": 1.0,
  "timings": {"adapter_s": 0.4, "denoise_s": 28.9, "encode_upload_s": 0.6}
}
```

## Coexisting with the async endpoint

The two projects use distinct SageMaker names (`wan22-ti2v-5b-realtime` vs
`wan22-ti2v-5b-async`) and the same base model artifact, so they can run
side-by-side against one S3 bucket. Both write generations under the same
`generations/` prefix.

Both deploys sync the handler code into the same `wan2.2-ti2v-5b-diffusers/code/`
prefix, but the files are kept byte-identical between the two projects -- the
per-endpoint defaults (frames/steps) live in each Model's environment variables,
not in the code -- so sync order does not matter.

Deploy either without touching the other; teardown one without affecting the other.

## Limits and knobs worth knowing

- **Real-time invocation cap:** 60 s (hard-capped by SageMaker; not configurable).
  Severs the response connection only -- the worker runs on; see the cap section above.
- **Response body cap:** ~6 MB. Not a concern here -- the video is uploaded to S3
  and the response only carries its URI.
- **Container-side timeout:** `TS_DEFAULT_RESPONSE_TIMEOUT=3600`. Kept generous so
  the SageMaker-side 60s cap fails first, which reads correctly as a timeout rather
  than as a worker crash.
- **Worker count:** `SAGEMAKER_MODEL_SERVER_WORKERS=1`. TorchServe otherwise spawns
  one worker per GPU, each loading its own ~24 GB copy of the pipeline.
- **Concurrency:** One generation at a time per instance -- the GPU is saturated by
  a single request. Additional inflight invocations queue at the runtime layer, and
  can themselves hit the 60s cap while waiting.
- **Scale to zero:** Not supported for real-time endpoints. Cold starts are minutes.
- **Endpoint creation:** ~10 min end to end. Most of that is the 34 GB artifact
  download; the pipeline itself loads to GPU in ~4 s once the files are local.
- **LoRA load:** ~1.9 s cold (S3 download), ~0.4 s warm (local cache), ~0.02 s to
  unload back to base.
- **Frame count** must satisfy `(n - 1) % 4 == 0` -- the Wan VAE compresses time 4x.
- **VAE precision:** fp32 while the rest of the pipeline is bf16. This split is
  prescribed by the model card; forcing the VAE to bf16 produces washed-out frames.
- **`flow_shift=5.0`** on `UniPCMultistepScheduler` is the documented setting for
  720p (3.0 is for 480p). Tunable via the `FLOW_SHIFT` env var.
- **Pipeline defaults** (overridable per request): 1280x704, 25 frames @ 24 fps,
  10 steps, `guidance_scale=5.0`. These are lower than the async project's defaults
  to fit inside the 60s cap.
- **Memory:** ~24 GB resident of 48 GB on the L40S. If you hit OOM at higher
  resolutions, `enable_model_cpu_offload()` is the next lever before a bigger
  instance -- but note offload adds seconds per step, which is expensive against a
  60s budget.

## Container image

`pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker-v1.84`

Same DLC as the async project. `requirements.txt` is fully pinned.
