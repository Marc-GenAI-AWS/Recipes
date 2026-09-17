"""Launch a segment's SFT, RL or teacher data-gen as a SageMaker training job — off the GB10.

Dependencies come from the prebuilt trainer image; the CODE comes from a fresh S3
channel staged at launch (so script edits never need an image rebuild). The base
Qwen3-8B is an S3 channel too (no HF-hub download inside the job).

  python pipeline/sagemaker/launch_job.py sft --segment ground --wait --download adapter-ground-8b-sft
  python pipeline/sagemaker/launch_job.py rl  --segment ground --adapter adapters/adapter-ground-8b-car \
         --wait --download adapter-ground-8b-rl
  python pipeline/sagemaker/launch_job.py sft --segment ground --instance ml.g6e.4xlarge   # capacity fallback
  # teacher data (Fable via Bedrock, verified by the harness on a CPU instance) -> data/<seg>_<tag>/
  python pipeline/sagemaker/launch_job.py gen --segment camera --tag train --seed 2 --n 96 --wait --download
  # specialist held-out eval / CaR: vLLM serves base + the LoRA adapter in-container (image tag vllm)
  python pipeline/sagemaker/launch_job.py serve --segment camera --adapter adapters/adapter-camera-8b-sft \
         --tag camera-spec-sft --seed 1 --n 24 --workers 3 --wait --download
  python pipeline/sagemaker/launch_job.py serve --segment camera --adapter adapters/adapter-camera-8b-sft \
         --tag car --seed 3 --n 96 --reviser fable --wait --download

Channels -> /opt/ml/input/data/{code,base,train,adapter}; the job copies code to /tmp/code
(writable) and runs the script there; the adapter is written to /opt/ml/model and
uploaded by SageMaker as model.tar.gz (downloaded + extracted with --download).
gen jobs write phase1/ into /opt/ml/checkpoints, which SageMaker syncs continuously to
s3://.../gen/<seg>_<tag>/ — rows survive a failed job and a relaunch resumes by id.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.config import REGION, BUCKET, S3_PREFIX as PREFIX, ROLE, image  # noqa: E402

IMAGE = image("latest")
BASE_S3 = f"s3://{BUCKET}/{PREFIX}/base/qwen3-8b/"   # staged by scripts/stage_base_model.py
# director: the best verified specialist per segment (held-out evals, 2026-09-15). Fauna is a Qwen3.8-27B LoRA whose keys
# were remapped for vLLM's multimodal Qwen3_5 loader (phase1/remap_lora_keys.py) — the unmapped adapter is silently ignored.
DIRECTOR_ADAPTERS = {"sky": "adapter-sky-8b-car", "ground": "adapter-ground-8b-car", "camera": "adapter-camera-8b-sft",
                     "vegetation": "adapter-vegetation-8b-car2", "effects": "adapter-effects-8b-car",
                     "fauna": "adapter-fauna-27b-vis-vl"}
REPO = Path(__file__).resolve().parents[2]
DEFAULT_INSTANCE = {"sft": "ml.g6e.2xlarge", "rl": "ml.g6e.4xlarge", "gen": "ml.c6i.8xlarge",
                    "serve": "ml.g6e.4xlarge",   # serve: L40S for vLLM + 16 vCPU for 4 render slots
                    "script": "ml.c6i.8xlarge"}  # script: CPU-only render/analysis jobs

sm = boto3.client("sagemaker", region_name=REGION)


def s3_sync(local: Path, uri: str) -> str:
    subprocess.run(["aws", "s3", "sync", str(local), uri, "--region", REGION, "--only-show-errors"], check=True)
    return uri


def stage_code(job: str, script: str) -> str:
    """Stage repo code + a run.sh holding the job command (ContainerArguments elements
    are capped at 256 chars, so the command lives in the channel, not the API call)."""
    d = Path(tempfile.mkdtemp(prefix="job-code-")) / "code"
    d.mkdir(parents=True)
    (d / "run.sh").write_text("#!/bin/bash\n" + script + "\n")
    shutil.copytree(REPO / "scenes", d / "scenes", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(REPO / "vendor", d / "vendor")
    rf = d / "pipeline" / "harness"
    rf.mkdir(parents=True)
    for fn in ("harness.py", "judge.py"):
        shutil.copy(REPO / "pipeline" / "harness" / fn, rf / fn)
    (d / "pipeline/training").mkdir()
    for p in (REPO / "pipeline/training").glob("*.py"):
        shutil.copy(p, d / "pipeline/training" / p.name)
    demo = REPO / "docs" / "specialist-demo"   # small HTML demo builds, for render-check scripts
    if demo.exists():
        shutil.copytree(demo, d / "docs" / "specialist-demo")
    return s3_sync(d, f"s3://{BUCKET}/{PREFIX}/jobs/{job}/code/")


def channel(name: str, uri: str) -> dict:
    return {"ChannelName": name, "InputMode": "File", "DataSource": {"S3DataSource": {
        "S3DataType": "S3Prefix", "S3Uri": uri, "S3DataDistributionType": "FullyReplicated"}}}


def tail_logs(job: str, n: int = 30) -> None:
    logs = boto3.client("logs", region_name=REGION)
    try:
        streams = logs.describe_log_streams(logGroupName="/aws/sagemaker/TrainingJobs",
                                            logStreamNamePrefix=job)["logStreams"]
        for s in streams[:1]:
            ev = logs.get_log_events(logGroupName="/aws/sagemaker/TrainingJobs",
                                     logStreamName=s["logStreamName"], limit=n, startFromHead=False)["events"]
            for e in ev:
                print("   |", e["message"].rstrip()[:220])
    except Exception as e:  # noqa: BLE001
        print("   (no logs yet:", str(e)[:80], ")")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["sft", "rl", "gen", "serve", "script", "director"])
    ap.add_argument("--cmd", default=None,
                    help="script: shell command run from the repo root in the container (writes under phase1/)")
    ap.add_argument("--segment", required=True)
    ap.add_argument("--instance", default=None)
    ap.add_argument("--adapter", default=None, help="local LoRA dir to init from (required for rl)")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--num-prompts", type=int, default=32)
    ap.add_argument("--rollouts", type=int, default=6)
    ap.add_argument("--max-hours", type=float, default=8)
    # gen
    ap.add_argument("--tag", default="train")
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--n", type=int, default=96)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--render-slots", type=int, default=4)
    # serve (specialist eval / CaR)
    ap.add_argument("--reviser", default=None, help="serve: fable for CaR; default = the specialist self-revises")
    ap.add_argument("--image-tag", default=None, help="trainer image tag (serve defaults to vllm)")
    ap.add_argument("--base", default="qwen3-8b", help="base model dir under s3://…/threejs-specialist/base/ (e.g. qwen3.8-27b)")
    ap.add_argument("--tp", type=int, default=1, help="serve: vLLM tensor-parallel size (GPUs); sft/rl stay on GPU 0")
    ap.add_argument("--plans", default=None, help="director: plan json under data/plans/")
    ap.add_argument("--fauna-base", default="qwen3.8-27b", help="director: base model dir for the fauna specialist")
    ap.add_argument("--attempts", type=int, default=3, help="director: generations per segment before host fallback")
    # serve memory knobs: defaults suit a 48 GB L40S (g6e); on a 24 GB L4 (ml.g6.*) use e.g.
    # --gpu-util 0.95 --max-num-seqs 2 --enforce-eager (8B bf16 weights ~16 GB leave ~5 GB of KV cache)
    ap.add_argument("--gpu-util", type=float, default=0.85)
    ap.add_argument("--max-model-len", type=int, default=20000)
    ap.add_argument("--max-num-seqs", type=int, default=8)
    ap.add_argument("--enforce-eager", action="store_true", help="serve: skip CUDA graphs (saves GPU memory)")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--download", nargs="?", const="", default=None,
                    help="sft/rl: adapters/<dir> to extract the adapter into; gen/serve: flag, syncs data/<seg>_<tag>/")
    args = ap.parse_args()
    # serve without --adapter = the BASE model as generator (no LoRA): used to test whether a capable base can write
    # layers for a host it was never trained on
    if args.stage == "rl" and not args.adapter:
        ap.error("rl needs --adapter")

    instance = args.instance or DEFAULT_INSTANCE[args.stage]
    # instance size + random suffix: two launches in the same second (racing copies across capacity
    # pools) otherwise get identical names and the second fails with ResourceInUse
    import secrets
    size = instance.rsplit(".", 1)[-1].replace("xlarge", "x")
    job = f"tjs-{args.segment}-{args.stage}-{time.strftime('%m%d-%H%M%S')}-{size}-{secrets.token_hex(2)}"[:63]
    root = f"s3://{BUCKET}/{PREFIX}/jobs/{job}"
    base_s3 = f"s3://{BUCKET}/{PREFIX}/base/{args.base}/"
    channels = [] if args.stage in ("gen", "script") else [channel("base", base_s3)]
    if args.stage == "director":
        if not args.plans:
            ap.error("director needs --plans")
        channels.append(channel("base27", f"s3://{BUCKET}/{PREFIX}/base/{args.fauna_base}/"))
        staged = Path(tempfile.mkdtemp(prefix="job-adapters-"))
        for seg_name, adapter_dir in DIRECTOR_ADAPTERS.items():
            shutil.copytree(REPO / "pipeline/training" / adapter_dir, staged / seg_name)
        channels.append(channel("adapters", s3_sync(staged, f"{root}/adapters/")))
    if args.stage == "script" and not args.cmd:
        ap.error("script needs --cmd")
    image = IMAGE.rsplit(":", 1)[0] + ":" + (args.image_tag or {"serve": "vllm", "director": "vllm29"}.get(args.stage, "latest"))
    gen_s3 = f"s3://{BUCKET}/{PREFIX}/gen/{args.segment}_{args.tag}/"

    if args.stage == "sft":
        data = Path(tempfile.mkdtemp(prefix="job-data-"))
        for split in ("train", "val"):
            src = REPO / "phase1" / f"{args.segment}_sft_{split}.jsonl"
            if not src.exists():
                print("missing", src, "- run build_segment_sft.py first"); return 1
            shutil.copy(src, data / src.name)
        channels.append(channel("train", s3_sync(data, f"{root}/train/")))
    if args.adapter:
        channels.append(channel("adapter", s3_sync(REPO / args.adapter, f"{root}/adapter/")))

    D = "/opt/ml/input/data"
    if args.stage == "sft":
        cmd = (f"python pipeline/training/sft_local.py --model {D}/base "
               f"--data {D}/train/{args.segment}_sft_train.jsonl --eval-data {D}/train/{args.segment}_sft_val.jsonl "
               f"--out /opt/ml/model --epochs {args.epochs}"
               + (f" --init-adapter {D}/adapter" if args.adapter else ""))
    elif args.stage == "rl":
        cmd = (f"python pipeline/training/train_segment_rl.py --segment {args.segment} --model {D}/base "
               f"--init-adapter {D}/adapter --out /opt/ml/model "
               f"--num-prompts {args.num_prompts} --rollouts {args.rollouts}")
    elif args.stage == "serve":
        # same sampling as local evals (gen_sky_baseline: temp 0.7, top_p 0.8, no thinking); LoRA
        # served on the base instead of a merged copy — no 16 GB merged upload per specialist
        gen_model = "spec" if args.adapter else "base"
        cmd = (f"/opt/vllm/bin/vllm serve {D}/base --served-model-name base "
               + (f"--enable-lora --max-lora-rank 64 --lora-modules spec={D}/adapter " if args.adapter else "")
               + f"--gpu-memory-utilization {args.gpu_util} "
               f"--max-model-len {args.max_model_len} --max-num-seqs {args.max_num_seqs} "
               f"--tensor-parallel-size {args.tp} "
               + ("--enforce-eager " if args.enforce_eager else "")
               + "--enable-prefix-caching --host 127.0.0.1 --port 8001 > /tmp/vllm.log 2>&1 &\n"
               "for i in $(seq 1 180); do curl -sf localhost:8001/v1/models >/dev/null && break; sleep 5; done\n"
               "curl -sf localhost:8001/v1/models || { echo SERVER-FAILED; tail -40 /tmp/vllm.log; exit 1; }\n"
               "mkdir -p /opt/ml/checkpoints/phase1 && ln -sfn /opt/ml/checkpoints/phase1 phase1\n"
               f"python pipeline/teacher.py --segment {args.segment} --generator {gen_model} "
               f"--endpoint http://localhost:8001/v1 --gen-model {gen_model} --tag {args.tag} "
               f"--seed {args.seed} --n {args.n} --workers {args.workers}"
               + (f" --reviser {args.reviser}" if args.reviser else "") + "\n"
               f"ls phase1/{args.segment}_{args.tag} | wc -l")
    elif args.stage == "director":
        # two vLLM servers on one instance: the 8B base + five 8B specialists on GPU 0, the 27B fauna base + its
        # specialist tensor-parallel on GPUs 1-2; the director fans each scene's segments out to them and renders on CPU
        A = f"{D}/adapters"
        loras8 = " ".join(f"{s}={A}/{s}" for s in DIRECTOR_ADAPTERS if s != "fauna")
        seg8 = [s for s in DIRECTOR_ADAPTERS if s != "fauna"]
        cmd = (f"CUDA_VISIBLE_DEVICES=0 /opt/vllm/bin/vllm serve {D}/base --served-model-name base --enable-lora "
               f"--max-lora-rank 64 --max-loras {len(seg8)} --lora-modules {loras8} --gpu-memory-utilization 0.9 "
               "--max-model-len 20000 --max-num-seqs 8 --enforce-eager --enable-prefix-caching "
               "--host 127.0.0.1 --port 8001 > /tmp/vllm8b.log 2>&1 &\n"
               f"CUDA_VISIBLE_DEVICES=1,2 /opt/vllm/bin/vllm serve {D}/base27 --served-model-name base27 --enable-lora "
               f"--max-lora-rank 64 --lora-modules fauna={A}/fauna --tensor-parallel-size 2 --gpu-memory-utilization 0.9 "
               "--max-model-len 20000 --max-num-seqs 3 --enforce-eager --host 127.0.0.1 --port 8002 > /tmp/vllm27b.log 2>&1 &\n"
               "for i in $(seq 1 240); do curl -sf localhost:8001/v1/models >/dev/null && curl -sf localhost:8002/v1/models >/dev/null && break; sleep 5; done\n"
               "curl -sf localhost:8001/v1/models || { echo SERVER-FAILED-8B; tail -40 /tmp/vllm8b.log; exit 1; }\n"
               "curl -sf localhost:8002/v1/models || { echo SERVER-FAILED-27B; tail -40 /tmp/vllm27b.log; exit 1; }\n"
               "mkdir -p /opt/ml/checkpoints/phase1 && ln -sfn /opt/ml/checkpoints/phase1 phase1\n"
               f"python pipeline/director.py --plans {args.plans} --out phase1/{args.segment}_{args.tag} "
               f"--attempts {args.attempts} --limit {args.n} "
               + " ".join(f"--endpoint {s}=http://localhost:8001/v1" for s in seg8)
               + " --endpoint fauna=http://localhost:8002/v1\n"
               f"ls -R phase1/{args.segment}_{args.tag} | head -60")
    elif args.stage == "script":
        # phase1/ is the synced output dir; the command writes its results anywhere under it
        cmd = ("mkdir -p /opt/ml/checkpoints/phase1 && ln -sfn /opt/ml/checkpoints/phase1 phase1\n"
               + args.cmd + "\nfind phase1 -type f | wc -l")
    else:
        cmd = ("mkdir -p /opt/ml/checkpoints/phase1 && ln -sfn /opt/ml/checkpoints/phase1 phase1\n"
               f"python pipeline/teacher.py --segment {args.segment} --tag {args.tag} "
               f"--seed {args.seed} --n {args.n} --workers {args.workers}\n"
               f"ls phase1/{args.segment}_{args.tag} | wc -l")
    script = f"set -e\ncp -r {D}/code /tmp/code\ncd /tmp/code\nnvidia-smi -L || true\nnproc\n{cmd}"
    channels.insert(0, channel("code", stage_code(job, script)))

    extra = {}
    # CUDA_VISIBLE_DEVICES=0: sft_local/train_segment_rl are single-GPU; on a multi-GPU instance
    # (ml.g6e.12xlarge, taken when 2xlarge had no capacity) HF Trainer wraps the model in
    # DataParallel and crashes ("index is on cuda:1, different from other tensors on cuda:0")
    # a tensor-parallel vLLM serve needs its GPUs visible; training stays pinned to GPU 0
    gpus = {"serve": ",".join(str(i) for i in range(args.tp)), "director": "0,1,2,3"}.get(args.stage, "0")
    env = {"CUDA_VISIBLE_DEVICES": gpus, "GPU_MEM_FRACTION": "0.9", "MIN_AVAIL_GB": "4", "RENDER_WORKERS": "6",
           "HF_HUB_OFFLINE": "1", "PYTHONUNBUFFERED": "1", "PRESENCE_CACHE": "/tmp/presence"}
    if args.stage in ("gen", "serve", "script", "director"):
        extra["CheckpointConfig"] = {"S3Uri": gen_s3, "LocalPath": "/opt/ml/checkpoints"}
        env["RENDER_SLOTS"] = str(args.render_slots)
    sm.create_training_job(
        TrainingJobName=job,
        AlgorithmSpecification={"TrainingImage": image, "TrainingInputMode": "File",
                                "ContainerEntrypoint": ["bash", f"{D}/code/run.sh"]},
        RoleArn=ROLE,
        InputDataConfig=channels,
        OutputDataConfig={"S3OutputPath": f"{root}/output/"},
        ResourceConfig={"InstanceType": instance, "InstanceCount": 1, "VolumeSizeInGB": 100},
        StoppingCondition={"MaxRuntimeInSeconds": int(args.max_hours * 3600)},
        Environment=env,
        **extra,
    )
    print(f"JOB {job} on {instance} ({image.rsplit(':', 1)[1]})"
          + (f" -> {gen_s3}" if args.stage in ("gen", "serve", "script", "director") else ""), flush=True)
    if not args.wait:
        return 0

    t0, last = time.time(), None
    while True:
        d = sm.describe_training_job(TrainingJobName=job)
        st, sec = d["TrainingJobStatus"], d.get("SecondaryStatus")
        if (st, sec) != last:
            print(f"  [{int(time.time()-t0)}s] {st} / {sec}", flush=True)
            last = (st, sec)
        if st in ("Completed", "Failed", "Stopped"):
            break
        time.sleep(60)
    if args.stage in ("gen", "serve", "script", "director") and args.download is not None:   # rows are in S3 even if the job failed
        if args.stage == "script":   # a script may write anywhere under phase1/
            dest = REPO / "phase1"
            src = f"{gen_s3}phase1/"
        else:
            dest = REPO / "phase1" / f"{args.segment}_{args.tag}"
            src = f"{gen_s3}phase1/{args.segment}_{args.tag}/"
        subprocess.run(["aws", "s3", "sync", src, str(dest), "--region", REGION, "--only-show-errors"], check=True)
        print("SYNCED ->", dest, flush=True)
    if st != "Completed":
        print("FAILED:", d.get("FailureReason", "")[:300]); tail_logs(job); return 1
    print(f"billable {d.get('BillableTimeInSeconds', 0)}s", flush=True)
    if args.stage in ("sft", "rl") and args.download:
        art = d["ModelArtifacts"]["S3ModelArtifacts"]
        print("ARTIFACT", art, flush=True)
        tmp = Path(tempfile.mkdtemp(prefix="job-art-")) / "model.tar.gz"
        subprocess.run(["aws", "s3", "cp", art, str(tmp), "--region", REGION, "--only-show-errors"], check=True)
        dest = REPO / "pipeline/training" / args.download
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp) as tf:
            tf.extractall(dest)
        print("DOWNLOADED ->", dest, sorted(p.name for p in dest.iterdir()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
