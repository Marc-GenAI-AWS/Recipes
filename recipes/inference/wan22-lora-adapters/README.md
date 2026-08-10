# WAN 2.2 + LoRA Adapters on SageMaker Endpoints

**Serve the WAN 2.2 TI2V-5B text-to-video model on a SageMaker managed endpoint
with per-request LoRA adapter swapping — no custom container, no conversion code,
stock Diffusers APIs on the AWS-managed PyTorch DLC.**

The base model loads once at container start (~24 GB resident on one L40S). Each
request may name an `adapter_s3_uri`; the container downloads the LoRA on first
use, caches it, applies it with stock `load_lora_weights()`, and dials strength
with `adapter_scale`. Adding a new LoRA is an S3 upload — no redeploy.

## Use this when

- You have a WAN 2.2 5B LoRA (style or motion adapter) and want it behind a
  managed HTTPS endpoint rather than a self-managed GPU box
- You need **many adapters on one warm base model**, selected per request —
  SageMaker's managed multi-adapter feature (inference components) is text-LLM
  only and does not cover diffusion models
- You want the AWS-managed DLC path: no Docker build, fully pinned
  `requirements.txt`, blue/green updates via endpoint config swap
- **Not this recipe:** real-time *streaming* of intermediate frames (needs custom
  TorchServe code), or the 14B WAN variants (different architecture; these
  adapters and measurements are 5B-specific)

## Two variants — pick by generation length

Both variants share byte-identical handler code; the difference is entirely on
the SageMaker side. Endpoint names are distinct, so they can run side by side
against one bucket.

| | [`realtime/`](realtime/) | [`async/`](async/) |
|---|---|---|
| Invocation cap | **60 s (hard)** | 60 min |
| Result delivery | Inline on the same call | Written to S3, poll for it |
| Fits at defaults | 25 frames / 10 steps (~30 s warm) | 49 frames / 30 steps (minutes) |
| Request queueing | None (429 on overload) | Managed |
| Scale to zero | No | Yes |
| Use for | Interactive "generate now" UIs | Full-quality or batch generation |

If a single generation might exceed 60 seconds, use `async/`. When in doubt,
start with `async/` — it has no request-size cliff.

## Results / validation

Measured on `ml.g6e.8xlarge` (1x L40S), 1280x704, warm worker:

| Metric | Value |
|---|---|
| Denoise speed | ~1.5 s/step at 25 frames |
| 25 frames / 10 steps end-to-end | ~30 s |
| 49 frames / 30 steps end-to-end | several minutes (async only) |
| LoRA apply | ~1.9 s cold (S3 fetch), ~0.4 s warm, ~0.02 s unload |
| Endpoint creation | ~10 min (dominated by the 34 GB model download) |
| GPU memory | ~24 GB resident of 48 GB |

## One-time setup (applies to both variants)

**1. Set your account specifics in `deploy/config.py`.** Each variant has its own
copy of the file; the block to edit is marked `CUSTOMER SETUP` at the top.

| Field | Set it to |
|---|---|
| `REGION` | Region for the endpoint, bucket, and container image. If it is not `us-west-2`, also update `INFERENCE_IMAGE_URI` — the DLC image URI is region-scoped; look yours up in the [DLC table](https://github.com/aws/deep-learning-containers/blob/master/available_images.md) |
| `BUCKET` | An S3 bucket you own, in `REGION`. Every other S3 URI derives from it |
| `ROLE_ARN` | A SageMaker execution role that trusts `sagemaker.amazonaws.com`, with `AmazonSageMakerFullAccess` (or equivalent), S3 read on the bucket, and S3 write on its `generations/` prefix (plus `async/` for the async variant) |

You also need AWS credentials on the deploying machine
(`aws sts get-caller-identity` should return the expected account) and service
quota for `ml.g6e.8xlarge` endpoint usage in the region.

**2. Upload the base model (~34 GB) to your bucket.** It must be the
Diffusers-format repo — the original research-format repo does not load:

```bash
pip install -U "huggingface_hub[cli]"
hf download Wan-AI/Wan2.2-TI2V-5B-Diffusers --local-dir wan2.2-ti2v-5b-diffusers
aws s3 sync wan2.2-ti2v-5b-diffusers s3://amzn-s3-demo-bucket/wan2.2-ti2v-5b-diffusers/
```

The prefix name must match `BASE_MODEL_S3_URI` in `config.py` (it derives from
`BUCKET`, so keeping the name `wan2.2-ti2v-5b-diffusers/` means no edit).

**3. Upload at least one LoRA adapter** — or plan to invoke with `--no-adapter`.
The two adapters validated for this recipe are public Hugging Face repos:

```bash
hf download AlekseyCalvin/HSToric_Color_Wan2.2_5B_LoRA_BySilverAgePoets --local-dir hstoric-color
aws s3 cp hstoric-color/ s3://amzn-s3-demo-bucket/loras/hstoric-color/ \
    --recursive --exclude "*" --include "*.safetensors"

# optional second adapter (motion effect)
hf download ostris/wan22_5b_i2v_crush_it_lora --local-dir crush-it
aws s3 cp crush-it/ s3://amzn-s3-demo-bucket/loras/crush-it/ \
    --recursive --exclude "*" --include "*.safetensors"
```

`loras/hstoric-color/` is the default adapter URI in `config.py`; different
prefixes work too — update `DEFAULT_ADAPTER_S3_URI` or pass `--adapter` at
invoke time.

**4. Validate the bucket before paying for a deploy** (seconds, no GPU):

```bash
cd async/deploy   # or realtime/deploy
python preflight.py
```

## Run it

After the one-time setup above, each variant deploys independently — see its
README for the measured request-size envelope and operational detail:

```bash
cd async   # or: cd realtime
cd deploy
python deploy.py                 # preflight -> upload code -> create -> verify (~10 min)
python 04_invoke.py "a prompt"
python teardown.py               # stops the billing
```

## Layout

```
wan22-lora-adapters/
├── async/       Async inference endpoint — 60 min cap, S3 results, scale to zero
└── realtime/    Real-time endpoint — inline responses inside the 60 s cap
```

A note on shared code: both variants sync `code/` into the same base-model S3
prefix, so the handler files are kept byte-identical between them. Endpoint
specific behavior (default frame/step counts) is injected via environment
variables in each variant's `01_create_model.py` — edit handler code in both
places or in neither.
