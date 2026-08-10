"""Invoke the real-time endpoint and print the result.

Unlike the async sibling, this calls `invoke_endpoint` directly -- the payload goes
on the wire, and the JSON response comes back inline. No S3 input/output plumbing,
no polling.

Real-time invocation is hard-capped at 60 seconds by SageMaker. The defaults below
(25 frames, 10 steps) fit inside that budget on a warm worker. Larger requests are
accepted but risk a ReadTimeoutError / ModelError from the runtime -- if a
generation might exceed 60s, use the async project instead.

Usage:
    python 04_invoke.py "your prompt here"
    python 04_invoke.py "..." --adapter s3://amzn-s3-demo-bucket/loras/hstoric-color/
    python 04_invoke.py "..." --no-adapter          # bare base model
    python 04_invoke.py "..." --adapter-scale 0.6   # dial the LoRA strength
"""

import argparse
import json
import sys
import time
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

import config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--adapter", default=config.DEFAULT_ADAPTER_S3_URI)
    ap.add_argument("--no-adapter", action="store_true")
    ap.add_argument("--adapter-scale", type=float, default=1.0)
    ap.add_argument("--height", type=int, default=704)
    ap.add_argument("--width", type=int, default=1280)
    # Defaults sized for the 60s real-time cap. See README for the safe envelope.
    ap.add_argument("--frames", type=int, default=25)
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--guidance", type=float, default=5.0)
    ap.add_argument("--seed", type=int)
    args = ap.parse_args()

    request_id = str(uuid.uuid4())
    payload = {
        "request_id": request_id,
        "prompt": args.prompt,
        "height": args.height,
        "width": args.width,
        "num_frames": args.frames,
        "num_inference_steps": args.steps,
        "guidance_scale": args.guidance,
    }
    if args.seed is not None:
        payload["seed"] = args.seed
    if not args.no_adapter:
        payload["adapter_s3_uri"] = args.adapter
        payload["adapter_scale"] = args.adapter_scale

    # boto3's default read_timeout (60s) matches the SageMaker cap, so leave it be.
    # Retries would just re-submit an identical generation after a timeout -- surface
    # the error to the caller instead.
    rt = boto3.client(
        "sagemaker-runtime",
        region_name=config.REGION,
        config=Config(retries={"max_attempts": 1}),
    )

    print(f"request  : {request_id}")
    print(f"adapter  : {payload.get('adapter_s3_uri', '(none - base model)')}")
    print(f"endpoint : {config.ENDPOINT_NAME}")
    print(f"budget   : 60s hard cap (frames={args.frames}, steps={args.steps})")
    print("\ninvoking (blocking until the video is generated)...", flush=True)

    t0 = time.time()
    try:
        resp = rt.invoke_endpoint(
            EndpointName=config.ENDPOINT_NAME,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload).encode(),
        )
    except ReadTimeoutError:
        elapsed = time.time() - t0
        print(f"\nTimed out after {elapsed:.0f}s.", file=sys.stderr)
        print("The 60s real-time cap is likely too tight for this request size.", file=sys.stderr)
        print("Reduce --frames / --steps, or use the async project.", file=sys.stderr)
        sys.exit(1)
    except ClientError as e:
        print(f"\nInvocation failed: {e}", file=sys.stderr)
        sys.exit(1)

    body = resp["Body"].read().decode()
    result = json.loads(body)
    print(f"\ndone in {time.time() - t0:.0f}s")
    print(json.dumps(result, indent=2))
    print(f"\nVideo: {result['video_s3_uri']}")


if __name__ == "__main__":
    main()
