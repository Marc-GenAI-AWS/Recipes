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

## Run it

Each variant is fully self-contained — see its README for prerequisites
(config fields, bucket layout, IAM role) and the measured request-size envelope:

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
