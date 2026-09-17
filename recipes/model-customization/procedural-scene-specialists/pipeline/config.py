"""Every environment-specific value in one place.

There is no separate "public" copy of this recipe: the code is environment-agnostic and your account details live in a
gitignored `.env`. Copy `.env.example` to `.env` and fill it in.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _req(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise SystemExit(f"{name} is not set — copy .env.example to .env and fill it in")
    return v


# ── AWS ────────────────────────────────────────────────────────────────────────────────────────
REGION = os.environ.get("AWS_REGION", "us-west-2")
ACCOUNT = os.environ.get("AWS_ACCOUNT_ID", "")
BUCKET = os.environ.get("SAGEMAKER_BUCKET", "")
ROLE = os.environ.get("SAGEMAKER_ROLE", "")
S3_PREFIX = os.environ.get("S3_PREFIX", "scene-specialists")
IMAGE_REPO = os.environ.get("TRAINER_IMAGE_REPO", "scene-specialist-trainer")


def image(tag: str = "latest") -> str:
    return f"{_req('AWS_ACCOUNT_ID')}.dkr.ecr.{REGION}.amazonaws.com/{IMAGE_REPO}:{tag}"


def s3(*parts: str) -> str:
    return f"s3://{_req('SAGEMAKER_BUCKET')}/{S3_PREFIX}/" + "/".join(p.strip('/') for p in parts if p)


# ── models ─────────────────────────────────────────────────────────────────────────────────────
# The teacher writes the training data. A frontier model via Bedrock works; so does a large open model served on your
# own GPUs — measured at parity on this task (see README "Choosing a teacher"), and cheaper per usable layer.
TEACHER = os.environ.get("TEACHER_MODEL", "us.anthropic.claude-fable-5-1")
TEACHER_ENDPOINT = os.environ.get("TEACHER_ENDPOINT", "")      # set to serve the teacher yourself instead of Bedrock
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "us.anthropic.claude-opus-5")
JUDGE_ENDPOINT = os.environ.get("JUDGE_ENDPOINT", "")
BASE_MODEL = os.environ.get("BASE_MODEL", "Qwen/Qwen3-8B")
BASE_MODEL_LARGE = os.environ.get("BASE_MODEL_LARGE", "Qwen/Qwen3.8-27B")

# ── local paths ────────────────────────────────────────────────────────────────────────────────
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))
ADAPTERS = Path(os.environ.get("ADAPTER_DIR", ROOT / "adapters"))
SCENES = ROOT / "scenes"

# ── evaluation protocol (change these and your numbers stop being comparable) ───────────────────
EVAL_SEED = 1          # held-out brief seed — never generate training data with it
EVAL_N = 24
RENDER_SLOTS = int(os.environ.get("RENDER_SLOTS", "4"))
