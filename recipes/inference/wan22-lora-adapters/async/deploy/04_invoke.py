"""Invoke the async endpoint and wait for the result.

Async inference takes its payload from S3: this uploads the request, calls
invoke_endpoint_async, then polls the returned OutputLocation until the result
(or the failure record) appears.

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
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

import config


def _split(uri: str) -> tuple[str, str]:
    p = urlparse(uri)
    return p.netloc, p.path.lstrip("/")


def _wait(s3, uri: str, timeout: int) -> bytes | None:
    bucket, key = _split(uri)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            return s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                raise
        time.sleep(5)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--adapter", default=config.DEFAULT_ADAPTER_S3_URI)
    ap.add_argument("--no-adapter", action="store_true")
    ap.add_argument("--adapter-scale", type=float, default=1.0)
    ap.add_argument("--height", type=int, default=704)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--frames", type=int, default=49)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--guidance", type=float, default=5.0)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--timeout", type=int, default=3600)
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

    s3 = boto3.client("s3", region_name=config.REGION)
    rt = boto3.client("sagemaker-runtime", region_name=config.REGION)

    in_bucket, in_prefix = _split(config.ASYNC_INPUT_PREFIX)
    in_key = f"{in_prefix.rstrip('/')}/{request_id}.json"
    s3.put_object(
        Bucket=in_bucket, Key=in_key,
        Body=json.dumps(payload).encode(), ContentType="application/json",
    )
    input_location = f"s3://{in_bucket}/{in_key}"
    print(f"request  : {request_id}")
    print(f"adapter  : {payload.get('adapter_s3_uri', '(none - base model)')}")
    print(f"input    : {input_location}")

    resp = rt.invoke_endpoint_async(
        EndpointName=config.ENDPOINT_NAME,
        InputLocation=input_location,
        ContentType="application/json",
        InvocationTimeoutSeconds=min(args.timeout, 3600),
    )
    out_uri, err_uri = resp["OutputLocation"], resp.get("FailureLocation")
    print(f"output   : {out_uri}")
    print("\nwaiting for generation (polling every 5s)...", flush=True)

    t0 = time.time()
    while time.time() - t0 < args.timeout:
        body = _wait(s3, out_uri, timeout=10)
        if body is not None:
            result = json.loads(body)
            print(f"\ndone in {time.time() - t0:.0f}s")
            print(json.dumps(result, indent=2))
            print(f"\nVideo: {result['video_s3_uri']}")
            return
        if err_uri:
            bucket, key = _split(err_uri)
            try:
                err = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode()
                print(f"\nFAILED after {time.time() - t0:.0f}s:\n{err}", file=sys.stderr)
                sys.exit(1)
            except ClientError:
                pass
        print(f"  ... {time.time() - t0:.0f}s", flush=True)

    print(f"\nTimed out after {args.timeout}s.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
