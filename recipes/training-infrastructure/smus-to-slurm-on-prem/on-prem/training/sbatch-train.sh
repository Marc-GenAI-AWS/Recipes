#!/usr/bin/env bash
#SBATCH --job-name=smus-train
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=%x-%j.out
#SBATCH --error=%x-%j.err

# Runs on-prem/training/train.py as a Slurm job.
# This script is what a SMUS Workflows DAG submits to slurmrestd.
#
# Env the submitter (DAG or notebook) is expected to set:
#   MLFLOW_TRACKING_URI          SMUS managed MLflow endpoint
#   MLFLOW_EXPERIMENT_NAME       optional; defaults to "smus-to-dgx"
#   AWS_ACCESS_KEY_ID / ...      credentials that can SigV4-sign MLflow calls
#   EPOCHS, BATCH_SIZE, LR       optional hyperparameters
#
# For standalone testing on the DGX (no SMUS yet), run:
#   sbatch on-prem/training/sbatch-train.sh

set -euo pipefail

EPOCHS="${EPOCHS:-5}"
BATCH_SIZE="${BATCH_SIZE:-128}"
LR="${LR:-0.001}"
SUBSET_ARG=""
[[ -n "${SUBSET:-}" ]] && SUBSET_ARG="--subset ${SUBSET}"

# Slurm copies this script to a scratch dir, so BASH_SOURCE won't resolve to
# the repo. Prefer an explicit TRAIN_DIR from the submitter; fall back to
# SLURM_SUBMIT_DIR/on-prem/training if the job was submitted from a repo root.
TRAIN_DIR="${TRAIN_DIR:-${SLURM_SUBMIT_DIR:-.}/on-prem/training}"
HERE="$TRAIN_DIR"

echo "node:    $(hostname)"
echo "gpu:     ${CUDA_VISIBLE_DEVICES:-unset}"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

# The job is intentionally submitted as a POSIX user (not the `slurm` service
# user) so it inherits that user's pre-installed torch / torchvision and their
# writable home — avoids re-downloading multi-GB CUDA wheels on every run.
# Fail fast with an actionable message if torch isn't there.
if ! python3.11 -c 'import torch, torchvision' 2>/dev/null; then
  echo "ERROR: torch / torchvision not importable for $(id -un) with python3.11." >&2
  echo "       Install once as this user before submitting jobs, e.g.:" >&2
  echo "         python3.11 -m pip install --user torch torchvision" >&2
  echo "       (pick the wheel that matches your CUDA / arch from pytorch.org)" >&2
  exit 1
fi

# Installs the MLflow client used to log to the SMUS managed MLflow tracking
# server. Versions intentionally unpinned — match whatever your SMUS managed
# MLflow server supports. Pin here if you hit a client/server skew.
python3.11 -m pip install --user --quiet mlflow sagemaker-mlflow

python3.11 "$HERE/train.py" \
  --epochs "$EPOCHS" \
  --batch-size "$BATCH_SIZE" \
  --lr "$LR" \
  $SUBSET_ARG \
  --run-name "slurm-${SLURM_JOB_ID:-local}"
