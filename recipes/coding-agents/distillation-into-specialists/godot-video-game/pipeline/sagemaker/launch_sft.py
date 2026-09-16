"""Launch the specialist SFT as a SageMaker training job.

    pipeline/.venv/bin/python pipeline/sagemaker/launch_sft.py --data pipeline/runs/sky1/sft --segment sky
    ... --dry-run   prints what would be launched, uploads nothing

Uses the PyTorch DLC with requirements.txt (TRL/PEFT) so no custom image is
needed. A 7B LoRA fits a single ml.g5.2xlarge (A10G 24 GB) at 6k tokens;
ml.g6e.2xlarge (L40S 48 GB) is the comfortable choice. Spot is on by default.
"""
import argparse
import os
import time
from pathlib import Path

import boto3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import AWS_REGION as REGION, BASE_MODEL, SAGEMAKER_BUCKET as BUCKET, SAGEMAKER_ROLE as ROLE, S3_PREFIX as PREFIX


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dir with train.jsonl / val.jsonl from build_sft.py")
    ap.add_argument("--segment", default="sky")
    ap.add_argument("--model", default=BASE_MODEL)
    ap.add_argument("--instance", default="ml.g6e.2xlarge")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--spot", type=int, default=1)
    ap.add_argument("--max-hours", type=float, default=3.0)
    # Sep 15: at 6144 tokens 528/529 props and 207/239 ground examples were cut (props contract alone is 5.3k
    # tokens; repair and revision examples kept no answer tokens). Longest props example 13,059; sky/veg/water < 6.5k.
    ap.add_argument("--max-len", type=int, default=14336, help="training sequence cut-off in tokens (contract + prompt + answer)")
    ap.add_argument("--liger", type=int, default=1, help="fused linear cross-entropy (a 7B at 14k tokens OOMed a 48 GB GPU without it)")
    ap.add_argument("--max-steps", type=int, default=-1, help="smoke test: stop after N optimizer steps and skip the merge")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M")
    job = f"scene-{a.segment}-sft-{stamp}" if a.max_steps < 0 else f"scene-{a.segment}-smoke-{stamp}"
    s3_data = f"s3://{BUCKET}/{PREFIX}/{a.segment}/datasets/{stamp}"
    s3_out = f"s3://{BUCKET}/{PREFIX}/{a.segment}/models"
    hp = {"model": a.model, "epochs": a.epochs, "lr": 1.5e-4, "max-len": a.max_len, "lora-r": 32, "merge": 1, "liger": a.liger}
    if a.max_steps > 0:
        hp.update({"max-steps": a.max_steps, "merge": 0})
    print(f"job          {job}\ninstance     {a.instance} (spot={bool(a.spot)})\nbase model   {a.model}\n"
          f"data         {a.data} -> {s3_data}\noutput       {s3_out}\nhyperparams  {hp}")
    if a.dry_run:
        print("dry run: nothing launched")
        return

    import sagemaker
    from sagemaker.pytorch import PyTorch
    sess = sagemaker.Session(boto3.Session(region_name=REGION))
    data = Path(a.data)
    train_uri = sess.upload_data(str(data / "train.jsonl"), bucket=BUCKET, key_prefix=f"{PREFIX}/{a.segment}/datasets/{stamp}/train")
    val_uri = sess.upload_data(str(data / "val.jsonl"), bucket=BUCKET, key_prefix=f"{PREFIX}/{a.segment}/datasets/{stamp}/val")
    est = PyTorch(
        entry_point="train_sft.py",
        source_dir=str(Path(__file__).parent),
        role=ROLE,
        framework_version="2.6",
        py_version="py312",
        instance_type=a.instance,
        instance_count=1,
        hyperparameters=hp,
        output_path=s3_out,
        base_job_name=job,
        use_spot_instances=bool(a.spot),
        max_run=int(a.max_hours * 3600),
        max_wait=int(a.max_hours * 3600) if a.spot else None,
        environment={"HF_HOME": "/tmp/hf", "TOKENIZERS_PARALLELISM": "false",
                     "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"},   # the 14k OOM had 6 GB reserved but unallocated
        sagemaker_session=sess,
        disable_profiler=True,
    )
    est.fit({"train": train_uri.rsplit("/", 1)[0], "val": val_uri.rsplit("/", 1)[0]}, job_name=job, wait=False)
    print(f"launched {job}; model artifact will land under {s3_out}/{job}/output/model.tar.gz")
    print(f"follow:  aws sagemaker describe-training-job --training-job-name {job} --query TrainingJobStatus")


if __name__ == "__main__":
    main()
