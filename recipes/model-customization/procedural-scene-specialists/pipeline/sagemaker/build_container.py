"""Build the x86 training+verifier image via CodeBuild (the GB10 is arm64 and
can't cross-build). Stages a minimal build context, zips it to S3, creates the
ECR repo + a privileged CodeBuild project (idempotent), starts the build, and
polls to completion. Runs entirely in AWS — no load on the GB10.

  python pipeline/sagemaker/build_container.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.config import REGION, ACCOUNT, BUCKET  # noqa: E402
S3_KEY = "scene-specialists/build/trainer-context.zip"
from pipeline.config import IMAGE_REPO as ECR_REPO  # noqa: E402
CB_PROJECT = f"{ECR_REPO}-build"
CB_ROLE = os.environ.get("CODEBUILD_ROLE", f"arn:aws:iam::{ACCOUNT}:role/service-role/AmazonSageMakerServiceCatalogProductsCodeBuildRole")

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def stage_context(dockerfile: str = "Dockerfile") -> Path:
    """Copy only what the Dockerfile COPYs (no venvs, adapters, checkpoints, demos)."""
    ctx = Path(tempfile.mkdtemp(prefix="trainer-ctx-"))
    shutil.copy(HERE / dockerfile, ctx / "Dockerfile")
    shutil.copy(HERE / "buildspec.yml", ctx / "buildspec.yml")
    shutil.copytree(REPO / "scenes", ctx / "scenes",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(REPO / "vendor", ctx / "vendor")
    (ctx / "pipeline" / "harness").mkdir(parents=True)
    for fn in ("harness.py", "judge.py"):
        shutil.copy(REPO / "pipeline" / "harness" / fn, ctx / "pipeline" / "harness" / fn)
    (ctx / "pipeline/training").mkdir()
    for p in (REPO / "pipeline/training").glob("*.py"):
        shutil.copy(p, ctx / "pipeline/training" / p.name)
    return ctx


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dockerfile", default="Dockerfile", help="e.g. Dockerfile.vllm (FROM :latest)")
    ap.add_argument("--tag", default="latest")
    args = ap.parse_args()
    s3, ecr, cb = (boto3.client(s, region_name=REGION) for s in ("s3", "ecr", "codebuild"))

    ctx = stage_context(args.dockerfile)
    zip_path = shutil.make_archive(str(ctx) + "-ctx", "zip", root_dir=ctx)
    size_mb = Path(zip_path).stat().st_size / 1e6
    s3.upload_file(zip_path, BUCKET, S3_KEY)
    print(f"context: {size_mb:.1f} MB -> s3://{BUCKET}/{S3_KEY}", flush=True)

    try:
        ecr.create_repository(repositoryName=ECR_REPO)
        print("created ECR repo", ECR_REPO)
    except ecr.exceptions.RepositoryAlreadyExistsException:
        pass

    project = {
        "name": CB_PROJECT,
        "source": {"type": "S3", "location": f"{BUCKET}/{S3_KEY}", "buildspec": "buildspec.yml"},
        "artifacts": {"type": "NO_ARTIFACTS"},
        "environment": {"type": "LINUX_CONTAINER", "image": "aws/codebuild/standard:7.0",
                        "computeType": "BUILD_GENERAL1_MEDIUM", "privilegedMode": True},
        "serviceRole": CB_ROLE,
        "timeoutInMinutes": 90,
    }
    try:
        cb.create_project(**project); print("created CodeBuild project", CB_PROJECT)
    except cb.exceptions.ResourceAlreadyExistsException:
        cb.update_project(**project); print("updated CodeBuild project", CB_PROJECT)

    build_id = cb.start_build(projectName=CB_PROJECT, environmentVariablesOverride=[
        {"name": "IMAGE_TAG", "value": args.tag, "type": "PLAINTEXT"}])["build"]["id"]
    print("build started:", build_id, flush=True)
    t0 = time.time()
    while True:
        b = cb.batch_get_builds(ids=[build_id])["builds"][0]
        status, phase = b["buildStatus"], b.get("currentPhase")
        print(f"  [{int(time.time()-t0)}s] {status} / {phase}", flush=True)
        if status != "IN_PROGRESS":
            break
        time.sleep(30)
    print("BUILD", status)
    if status != "SUCCEEDED":
        # surface the failing phase + log location for debugging
        for ph in b.get("phases", []):
            if ph.get("phaseStatus") == "FAILED":
                print("  failed phase:", ph.get("phaseType"), ph.get("contexts"))
        print("  logs:", b.get("logs", {}).get("deepLink"))
        return 1
    print(f"IMAGE {ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO}:{args.tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
