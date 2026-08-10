"""Shut the endpoint down. This is what stops the hourly billing.

    python teardown.py           # delete the endpoint, keep Model + EndpointConfig
    python teardown.py --all     # also delete Model + EndpointConfig
    python teardown.py --status  # show what currently exists, delete nothing

Keeping the Model and EndpointConfig is the default because they are free to retain
and make the next `deploy.py` a single API call rather than a rebuild. Use --all only
when you are changing the model artifact or container settings, since both names are
immutable and would otherwise need bumping in config.py.
"""

import argparse
import time

import boto3
from botocore.exceptions import ClientError

import config


def state(sm) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    try:
        out["endpoint"] = sm.describe_endpoint(
            EndpointName=config.ENDPOINT_NAME)["EndpointStatus"]
    except ClientError:
        out["endpoint"] = None
    for label, fn, kw in (
        ("config", sm.describe_endpoint_config, {"EndpointConfigName": config.ENDPOINT_CONFIG_NAME}),
        ("model", sm.describe_model, {"ModelName": config.MODEL_NAME}),
    ):
        try:
            fn(**kw)
            out[label] = "exists"
        except ClientError:
            out[label] = None
    return out


def show(s: dict[str, str | None]) -> None:
    print(f"  endpoint {config.ENDPOINT_NAME:<28} {s['endpoint'] or '(none)'}")
    print(f"  config   {config.ENDPOINT_CONFIG_NAME:<28} {s['config'] or '(none)'}")
    print(f"  model    {config.MODEL_NAME:<28} {s['model'] or '(none)'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also delete Model + EndpointConfig")
    ap.add_argument("--status", action="store_true", help="show state, change nothing")
    args = ap.parse_args()

    sm = boto3.client("sagemaker", region_name=config.REGION)
    s = state(sm)

    print("\ncurrent state:")
    show(s)
    if args.status:
        return

    print()
    if s["endpoint"]:
        sm.delete_endpoint(EndpointName=config.ENDPOINT_NAME)
        print(f"-> deleting endpoint {config.ENDPOINT_NAME} (billing stops)")
        for _ in range(60):
            if state(sm)["endpoint"] is None:
                break
            time.sleep(10)
        print("   deleted")
    else:
        print("-> no endpoint running; nothing is billing")

    if args.all:
        if s["config"]:
            sm.delete_endpoint_config(EndpointConfigName=config.ENDPOINT_CONFIG_NAME)
            print(f"-> deleted EndpointConfig {config.ENDPOINT_CONFIG_NAME}")
        if s["model"]:
            sm.delete_model(ModelName=config.MODEL_NAME)
            print(f"-> deleted Model {config.MODEL_NAME}")

    print("\nfinal state:")
    show(state(sm))
    print("\nRelaunch with:  python deploy.py")
    if not args.all:
        print("(Model + EndpointConfig kept, so relaunch is just the model download.)")
    print()


if __name__ == "__main__":
    main()
