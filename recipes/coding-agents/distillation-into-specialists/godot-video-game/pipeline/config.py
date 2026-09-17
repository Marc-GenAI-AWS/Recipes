"""CUSTOMER SETUP — the only file with anything specific to your account or machine.

Every value can also come from the environment, so nothing here needs editing if you
export the same names (see .env.example).
"""
import os
from pathlib import Path

# --- AWS -------------------------------------------------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
# The bucket training data and model artifacts live in, e.g. "sagemaker-us-west-2-123456789012"
SAGEMAKER_BUCKET = os.environ.get("SAGEMAKER_BUCKET", "REPLACE-ME-sagemaker-bucket")
# An execution role SageMaker assumes, e.g.
# "arn:aws:iam::123456789012:role/service-role/AmazonSageMaker-ExecutionRole-00000000T000000"
SAGEMAKER_ROLE = os.environ.get("SAGEMAKER_ROLE", "REPLACE-ME-sagemaker-execution-role-arn")
S3_PREFIX = os.environ.get("S3_PREFIX", "specialist-pipeline")

# --- the game the models write layers for ----------------------------------
# Clone the example game next to this recipe, or point GAME_DIR at it:
#   git clone --branch recipe-v1 https://github.com/Marc-GenAI-AWS/godot-game
# recipe-v1 is the tag this recipe was validated against.
GAME = Path(os.environ.get("GAME_DIR", Path(__file__).resolve().parents[1] / "godot-game" / "game"))
# Godot 4.7+ binary. A headless machine still needs a GPU and an X display for the captures.
GODOT = Path(os.environ.get("GODOT_BIN", "godot"))

# --- models ----------------------------------------------------------------
# Bedrock inference-profile ids. The teacher writes candidate layers, the judge scores
# the captures, the director turns a scene brief into per-segment briefs.
TEACHER_MODEL = os.environ.get("TEACHER_MODEL", "us.anthropic.claude-sonnet-5")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "us.anthropic.claude-sonnet-5")
DIRECTOR_MODEL = os.environ.get("DIRECTOR_MODEL", "us.anthropic.claude-fable-5-1")
# The base model each specialist is fine-tuned from.
BASE_MODEL = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-Coder-3B-Instruct")
