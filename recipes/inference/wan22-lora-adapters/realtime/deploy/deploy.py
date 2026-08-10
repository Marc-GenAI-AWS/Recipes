"""One-command deploy. Idempotent -- safe to re-run.

    python deploy.py              # preflight, then bring the endpoint up
    python deploy.py --skip-preflight
    python deploy.py --force-code # re-upload code even if the endpoint exists

Creates only what is missing. Because Model and EndpointConfig are immutable and
survive endpoint deletion, a relaunch after teardown is just the create-endpoint call
and the model download -- roughly 10 minutes.

Crucially, this does not trust EndpointStatus. An endpoint reports InService while its
worker is in a crash-restart loop, so the last step reads CloudWatch and confirms the
pipeline actually loaded.
"""

import argparse
import pathlib
import subprocess
import sys
import time

import boto3
from botocore.exceptions import ClientError

import config

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent / "code"
LOG_GROUP = f"/aws/sagemaker/Endpoints/{config.ENDPOINT_NAME}"


def sh(*args: str) -> None:
    subprocess.run(list(args), check=True)


def exists(fn, **kw) -> bool:
    try:
        fn(**kw)
        return True
    except ClientError:
        return False


def upload_code() -> None:
    dest = config.BASE_MODEL_S3_URI.rstrip("/") + "/code/"
    print(f"-> syncing code/ to {dest}")
    sh("aws", "s3", "sync", str(CODE_DIR), dest, "--region", config.REGION,
       "--delete", "--exclude", "__pycache__/*", "--only-show-errors")


def wait_for_worker(sm, logs, since_ms: int, timeout: int = 2400) -> bool:
    """Poll until the endpoint settles AND the worker proves it loaded.

    Both conditions must hold: EndpointStatus == InService, and the worker has
    printed "Pipeline ready" in a log stream created after `since_ms`. The worker
    typically prints "Pipeline ready" a few seconds before EndpointStatus flips
    from Creating to InService, so a naive `return status == "InService"` at the
    moment the log line appears will falsely report failure.

    The log-stream filter also matters: the log group outlives the endpoint, so
    stale streams from a previous deploy would otherwise be read as if they
    described this one.
    """
    deadline = time.time() + timeout
    last = None
    worker_ready = False
    while time.time() < deadline:
        status = sm.describe_endpoint(EndpointName=config.ENDPOINT_NAME)["EndpointStatus"]
        if status != last:
            print(f"   status={status}")
            last = status
        if status == "Failed":
            d = sm.describe_endpoint(EndpointName=config.ENDPOINT_NAME)
            print(f"!! FailureReason: {d.get('FailureReason')}")
            return False

        if not worker_ready:
            try:
                streams = [
                    s for s in logs.describe_log_streams(logGroupName=LOG_GROUP)["logStreams"]
                    if s.get("creationTime", 0) >= since_ms
                ]
            except ClientError:
                streams = []

            for st in streams:
                ev = logs.get_log_events(
                    logGroupName=LOG_GROUP, logStreamName=st["logStreamName"],
                    startFromHead=True, limit=800,
                )["events"]
                text = "\n".join(e["message"] for e in ev)
                if "Pipeline ready" in text:
                    line = next(l for l in text.splitlines() if "Pipeline ready" in l)
                    print(f"   worker: {line.split('MODEL_LOG - ')[-1].strip()}")
                    worker_ready = True
                    break
                for marker in ("Backend worker process died", "CUDA out of memory"):
                    if marker in text:
                        print(f"!! worker failed: {marker}")
                        for l in text.splitlines():
                            if any(k in l for k in ("Error", "error:")):
                                print(f"   {l.split('MODEL_LOG - ')[-1].strip()[:200]}")
                        return False

        if worker_ready and status == "InService":
            return True
        time.sleep(20)

    print("!! timed out waiting for the worker")
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--force-code", action="store_true")
    args = ap.parse_args()

    if not args.skip_preflight:
        print("== preflight")
        if subprocess.run([sys.executable, "preflight.py"]).returncode != 0:
            sys.exit(1)

    sm = boto3.client("sagemaker", region_name=config.REGION)
    logs = boto3.client("logs", region_name=config.REGION)

    print("== artifacts")
    ep_live = exists(sm.describe_endpoint, EndpointName=config.ENDPOINT_NAME)
    if args.force_code or not ep_live:
        upload_code()
    else:
        print("-> endpoint already up; skipping code sync (use --force-code to override)")

    if exists(sm.describe_model, ModelName=config.MODEL_NAME):
        print(f"-> Model {config.MODEL_NAME} exists")
    else:
        sh(sys.executable, "01_create_model.py")

    if exists(sm.describe_endpoint_config, EndpointConfigName=config.ENDPOINT_CONFIG_NAME):
        print(f"-> EndpointConfig {config.ENDPOINT_CONFIG_NAME} exists")
    else:
        sh(sys.executable, "02_create_endpoint_config.py")

    print("== endpoint")
    since_ms = int(time.time() * 1000)
    if ep_live:
        print(f"-> Endpoint {config.ENDPOINT_NAME} already exists")
    else:
        sm.create_endpoint(
            EndpointName=config.ENDPOINT_NAME,
            EndpointConfigName=config.ENDPOINT_CONFIG_NAME,
        )
        print(f"-> creating {config.ENDPOINT_NAME} (~10 min: 34 GB download + load)")

    if not wait_for_worker(sm, logs, since_ms):
        print("\nDEPLOY FAILED -- the endpoint is not serving. See CloudWatch:")
        print(f"  aws logs tail {LOG_GROUP} --region {config.REGION}")
        sys.exit(1)

    print(f"\nREADY: {config.ENDPOINT_NAME}")
    print(f"  instance : {config.INSTANCE_TYPE}")
    print(f"  adapter  : {config.DEFAULT_ADAPTER_S3_URI}")
    print("\nTry it:")
    print('  python 04_invoke.py "A steam train crossing a stone viaduct in the mountains" \\')
    print("      --frames 25 --steps 10 --seed 7")
    print("\nShut it down when you are done (it bills by the hour):")
    print("  python teardown.py")


if __name__ == "__main__":
    main()
