"""SageMaker PyTorch DLC handler for WAN 2.2 TI2V-5B with runtime LoRA swapping.

Runs on the AWS-managed PyTorch inference DLC as a plain request/response handler --
no custom TorchServe streaming code.

The base model is loaded once at container start from the Diffusers-format artifact
mounted at /opt/ml/model. Each request may name an `adapter_s3_uri`; the adapter is
downloaded, cached, and applied with the stock `load_lora_weights()`. The generated
MP4 is written to S3 and the response carries its URI.

This file is shared byte-for-byte between the async and real-time sibling projects:
both sync `code/` into the same base-model prefix, so whichever deploys last would
otherwise overwrite the other's handler. Everything endpoint-specific -- notably the
default frame/step counts, which must fit the real-time 60-second invocation cap on
one endpoint type but not the other -- is therefore injected as environment
variables by each project's 01_create_model.py, never edited here.
"""

import json
import logging
import os
import time
import uuid
from typing import Any

import boto3
import torch
from diffusers import AutoencoderKLWan, UniPCMultistepScheduler, WanPipeline
from diffusers.utils import export_to_video

from lora_cache import LoraCache

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "generations")

# The shipped scheduler_config.json already sets flow_shift=5.0, the documented value
# for this 720p model. Re-applying it here changes nothing by default; it exists so
# the shift can be retuned (e.g. 3.0 for 480p) via env without touching code.
FLOW_SHIFT = float(os.environ.get("FLOW_SHIFT", "5.0"))

# Generation defaults. Each project's 01_create_model.py injects its own values --
# async: 49 frames / 30 steps; real-time: 25 frames / 10 steps to fit the 60s
# invocation cap. The fallbacks below match the real-time numbers because those are
# safe on either endpoint type.
DEFAULT_HEIGHT = int(os.environ.get("DEFAULT_HEIGHT", "704"))
DEFAULT_WIDTH = int(os.environ.get("DEFAULT_WIDTH", "1280"))
DEFAULT_FRAMES = int(os.environ.get("DEFAULT_FRAMES", "25"))
DEFAULT_STEPS = int(os.environ.get("DEFAULT_STEPS", "10"))
DEFAULT_GUIDANCE = float(os.environ.get("DEFAULT_GUIDANCE", "5.0"))
DEFAULT_FPS = int(os.environ.get("DEFAULT_FPS", "24"))


def model_fn(model_dir: str) -> dict:
    log.info("Loading WAN 2.2 pipeline from %s", model_dir)
    t0 = time.time()

    # The Wan VAE is numerically fragile in low precision -- it is loaded in fp32
    # while the rest of the pipeline runs in bf16. This split is what the model
    # card prescribes; collapsing both to bf16 produces washed-out frames.
    vae = AutoencoderKLWan.from_pretrained(
        model_dir, subfolder="vae", torch_dtype=torch.float32
    )
    pipeline = WanPipeline.from_pretrained(
        model_dir, vae=vae, torch_dtype=torch.bfloat16
    )
    pipeline.scheduler = UniPCMultistepScheduler.from_config(
        pipeline.scheduler.config, flow_shift=FLOW_SHIFT
    )
    pipeline.to("cuda")
    # Tiling lives on the VAE, not the pipeline -- WanPipeline has no
    # `enable_vae_tiling()`. Calling it there raises AttributeError and kills the
    # worker; guarding that call with try/except would silently disable tiling.
    pipeline.vae.enable_tiling()

    log.info("Pipeline ready in %.1fs", time.time() - t0)
    return {
        "pipeline": pipeline,
        "lora_cache": LoraCache(),
        "s3": boto3.client("s3"),
    }


def input_fn(request_body: str | bytes, content_type: str) -> dict:
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    payload = json.loads(request_body)
    if "prompt" not in payload:
        raise ValueError("payload must include 'prompt'")
    return payload


def predict_fn(payload: dict, state: dict) -> dict[str, Any]:
    request_id = payload.get("request_id") or str(uuid.uuid4())
    pipeline = state["pipeline"]
    lora_cache: LoraCache = state["lora_cache"]

    adapter_uri = payload.get("adapter_s3_uri")
    adapter_scale = float(payload.get("adapter_scale", 1.0))
    timings: dict[str, float] = {}

    t0 = time.time()
    if adapter_uri:
        lora_cache.apply(pipeline, adapter_uri, scale=adapter_scale)
    else:
        lora_cache.clear(pipeline)
    timings["adapter_s"] = round(time.time() - t0, 2)

    seed = payload.get("seed")
    generator = (
        torch.Generator(device="cuda").manual_seed(int(seed)) if seed is not None else None
    )

    height = int(payload.get("height", DEFAULT_HEIGHT))
    width = int(payload.get("width", DEFAULT_WIDTH))
    num_frames = int(payload.get("num_frames", DEFAULT_FRAMES))
    fps = int(payload.get("fps", DEFAULT_FPS))

    # The Wan VAE compresses time by 4x, so the frame count must land on 4k+1.
    if (num_frames - 1) % 4 != 0:
        raise ValueError(f"num_frames must satisfy (n-1) % 4 == 0; got {num_frames}")

    log.info(
        "Generating request_id=%s adapter=%s %dx%d frames=%d",
        request_id, adapter_uri or "none", width, height, num_frames,
    )
    t0 = time.time()
    result = pipeline(
        prompt=payload["prompt"],
        negative_prompt=payload.get("negative_prompt") or None,
        height=height,
        width=width,
        num_frames=num_frames,
        num_inference_steps=int(payload.get("num_inference_steps", DEFAULT_STEPS)),
        guidance_scale=float(payload.get("guidance_scale", DEFAULT_GUIDANCE)),
        generator=generator,
    )
    timings["denoise_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    tmp_path = f"/tmp/{request_id}.mp4"
    export_to_video(result.frames[0], tmp_path, fps=fps)
    key = f"{OUTPUT_PREFIX}/{request_id}.mp4"
    try:
        state["s3"].upload_file(
            tmp_path, OUTPUT_BUCKET, key, ExtraArgs={"ContentType": "video/mp4"}
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    timings["encode_upload_s"] = round(time.time() - t0, 2)

    return {
        "request_id": request_id,
        "video_s3_uri": f"s3://{OUTPUT_BUCKET}/{key}",
        "adapter_s3_uri": adapter_uri,
        "adapter_scale": adapter_scale if adapter_uri else None,
        "resolution": [width, height],
        "num_frames": num_frames,
        "fps": fps,
        "timings": timings,
    }


def output_fn(prediction: dict, accept: str) -> tuple[str, str]:
    return json.dumps(prediction), "application/json"
