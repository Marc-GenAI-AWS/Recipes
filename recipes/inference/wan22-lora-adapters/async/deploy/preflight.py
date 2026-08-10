"""Validate the S3 artifacts before paying for a 10-minute deploy.

Every check here catches a failure that otherwise only surfaces after the container
has downloaded 34 GB and loaded the pipeline -- or, worse, that never raises at all
and just silently degrades output.

Runs in seconds. No torch, no GPU, boto3 + stdlib only.

    python preflight.py
"""

import json
import struct
import sys
from urllib.parse import urlparse

import boto3

import config

REQUIRED_ROOT = ["model_index.json"]
REQUIRED_DIRS = ["transformer/", "vae/", "text_encoder/", "tokenizer/", "scheduler/"]
REQUIRED_CODE = ["inference.py", "lora_cache.py", "requirements.txt"]

ok = True


def report(passed: bool, label: str, detail: str = "") -> None:
    global ok
    if not passed:
        ok = False
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")


def split(uri: str) -> tuple[str, str]:
    p = urlparse(uri)
    return p.netloc, p.path.lstrip("/")


def list_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys, token = [], None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        keys += [o["Key"][len(prefix):] for o in r.get("Contents", [])]
        if not r.get("IsTruncated"):
            return keys
        token = r["NextContinuationToken"]


def safetensors_keys(s3, bucket: str, key: str) -> list[str]:
    """Read a safetensors header via a ranged GET -- no need to pull the whole file."""
    head = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-7")["Body"].read()
    n = struct.unpack("<Q", head)[0]
    body = s3.get_object(Bucket=bucket, Key=key, Range=f"bytes=8-{8 + n - 1}")["Body"].read()
    return [k for k in json.loads(body) if k != "__metadata__"]


def convert_wan_keys(src: set[str], blocks: range) -> tuple[set[str], set[str]]:
    """Replicate diffusers' _convert_non_diffusers_wan_lora_to_diffusers name mapping."""
    consumed, targets = set(), set()
    for i in blocks:
        pairs = []
        for o, c in zip(["q", "k", "v", "o"], ["to_q", "to_k", "to_v", "to_out.0"]):
            pairs.append((f"blocks.{i}.self_attn.{o}", f"blocks.{i}.attn1.{c}"))
            pairs.append((f"blocks.{i}.cross_attn.{o}", f"blocks.{i}.attn2.{c}"))
        for o, c in zip(["ffn.0", "ffn.2"], ["net.0.proj", "net.2"]):
            pairs.append((f"blocks.{i}.{o}", f"blocks.{i}.ffn.{c}"))
        for s, d in pairs:
            for lk in ("lora_A", "lora_B", "lora_down", "lora_up"):
                k = f"{s}.{lk}.weight"
                if k in src:
                    consumed.add(k)
                    targets.add(d)
    return consumed, targets


def main() -> None:
    s3 = boto3.client("s3", region_name=config.REGION)
    bucket, prefix = split(config.BASE_MODEL_S3_URI)

    print(f"\nBase model: {config.BASE_MODEL_S3_URI}")
    keys = list_keys(s3, bucket, prefix)
    if not keys:
        report(False, "artifact exists", "prefix is empty")
        sys.exit(1)

    for f in REQUIRED_ROOT:
        report(f in keys, f"{f} present",
               "" if f in keys else "WanPipeline.from_pretrained needs Diffusers format")
    for d in REQUIRED_DIRS:
        report(any(k.startswith(d) for k in keys), f"{d} present")
    for f in REQUIRED_CODE:
        report(f"code/{f}" in keys, f"code/{f} present")

    # ftfy is an *optional* diffusers dep that WanPipeline hard-requires: it is imported
    # under `if is_ftfy_available()` but called unconditionally, so omitting it fails at
    # the first prompt encode, long after the endpoint reports healthy.
    try:
        reqs = s3.get_object(Bucket=bucket, Key=f"{prefix}code/requirements.txt")["Body"].read().decode()
        report("ftfy" in reqs, "ftfy pinned in requirements.txt",
               "" if "ftfy" in reqs else "WanPipeline calls ftfy.fix_text() unconditionally")
        unpinned = [ln.strip() for ln in reqs.splitlines()
                    if ln.strip() and not ln.startswith("#") and "==" not in ln]
        report(not unpinned, "all requirements pinned", ", ".join(unpinned))
    except Exception as e:
        report(False, "requirements.txt readable", str(e))

    # Real module names, to confirm converted LoRA keys land on something.
    real = set()
    try:
        idx = s3.get_object(
            Bucket=bucket, Key=f"{prefix}transformer/diffusion_pytorch_model.safetensors.index.json"
        )["Body"].read()
        real = {k.rsplit(".", 1)[0] for k in json.loads(idx)["weight_map"]}
        report(True, "transformer index readable", f"{len(real)} modules")
    except Exception as e:
        report(False, "transformer index readable", str(e))

    # Adapters
    lb, lp = split(config.LORA_PREFIX)
    adapters = sorted({k.split("/")[0] for k in list_keys(s3, lb, lp) if "/" in k})
    print(f"\nAdapters under {config.LORA_PREFIX} ({len(adapters)} found)")
    for name in adapters:
        print(f"\n  {name}/")
        wf = [k for k in list_keys(s3, lb, f"{lp}{name}/") if k.endswith(".safetensors")]
        if not wf:
            report(False, "has a .safetensors weight file")
            continue
        try:
            ks = safetensors_keys(s3, lb, f"{lp}{name}/{wf[0]}")
        except Exception as e:
            report(False, "header readable", str(e))
            continue

        if any(k.startswith("transformer.") for k in ks):
            report(True, "key format", "Diffusers-native, loads directly")
            continue
        if not any(k.startswith("diffusion_model.") for k in ks):
            report(False, "key format",
                   f"unsupported prefix (e.g. {sorted(ks)[0]}) -- diffusers would load NOTHING, silently")
            continue

        src = {k[len("diffusion_model."):] for k in ks}
        bl = {int(k.split(".")[1]) for k in src if k.startswith("blocks.")}
        consumed, targets = convert_wan_keys(src, range(min(bl), max(bl) + 1))
        report(True, "key format", "ai-toolkit/ComfyUI, auto-converted by diffusers")
        leftover = src - consumed
        report(not leftover, f"all {len(src)} tensors consumed",
               "" if not leftover else f"{len(leftover)} would be silently dropped")
        if real:
            missing = targets - real
            report(not missing, f"all {len(targets)} target modules exist",
                   "" if not missing else f"{len(missing)} do not exist in this base model")

    print()
    if ok:
        print("PREFLIGHT PASSED -- safe to deploy\n")
    else:
        print("PREFLIGHT FAILED -- fix the above before deploying\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
