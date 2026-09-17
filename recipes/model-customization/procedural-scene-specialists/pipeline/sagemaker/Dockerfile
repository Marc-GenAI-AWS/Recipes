# x86 SageMaker TRAINING + VERIFIER container for the Three.js specialist pipeline.
#
# One image, two jobs: SFT (sft_local.py) and RLVR (train_sky_rl.py, whose reward
# is the layer-harness — headless Chromium + the assembler — running IN-CONTAINER).
# The GB10 dev box is arm64, so this is built by CodeBuild (see build script).
#
# Base: HF PyTorch training DLC (torch 2.8 cu129, py312) so torch/CUDA are prebuilt.
FROM 763104351884.dkr.ecr.us-west-2.amazonaws.com/huggingface-pytorch-training:2.8-transformers4.56-gpu-py312-cu129-ubuntu22.04

# Chromium runtime libs (Ubuntu 22.04) for the render harness.
# Node 20 via NodeSource: Ubuntu 22.04's apt `nodejs` is v12, which lacks the
# `require('node:fs')` prefix scheme that assemble.cjs uses (MODULE_NOT_FOUND).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libx11-6 libxcb1 libxext6 libexpat1 libdbus-1-3 fonts-liberation \
    curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && node --version \
    && rm -rf /var/lib/apt/lists/*

# Python deps matching the local env that produced r1 / r2 / the RL run
# (torch stays the DLC's 2.8 — these must not pull a different torch)
RUN pip install --no-cache-dir \
    "transformers>=5.15,<6" "trl>=1.10,<2" "peft>=0.20,<1" datasets \
    playwright pillow boto3 \
    "flash-linear-attention==0.5.2"
# flash-linear-attention: Triton kernels for the linear-attention layers of qwen3_5 bases (Qwen3.8-27B);
# without it transformers falls back to a slow, memory-hungry torch path

# Bundle Chromium in the image (training filesystem is read-only-ish and offline-safe)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN playwright install chromium

# Repo layout mirrored under /opt/ml/code so REPO-relative paths in the scripts resolve:
#   pipeline/training/*.py, golden-scenes/ (contract, assembler, phase1 runners), vendor/ (offline three),
#   pipeline/harness/ (harness, judge)
WORKDIR /opt/ml/code
COPY golden-scenes/ /opt/ml/code/golden-scenes/
COPY vendor/ /opt/ml/code/vendor/
COPY pipeline/harness/harness.py pipeline/harness/judge.py \
     /opt/ml/code/pipeline/harness/
COPY pipeline/training/*.py /opt/ml/code/pipeline/training/

ENV HARNESS_THREE_LOCAL=/opt/ml/code/vendor/three.module.min.js \
    HARNESS_THREE_ADDONS=/opt/ml/code/vendor/three-addons \
    PYTHONUNBUFFERED=1 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# SageMaker training entry (the toolkit runs SAGEMAKER_PROGRAM; hyperparameters -> CLI args).
# Override per job, e.g. SAGEMAKER_PROGRAM=pipeline/training/sft_local.py for SFT.
ENV SAGEMAKER_PROGRAM=pipeline/training/train_sky_rl.py

# smoke: the harness + assembler must import and node must run
RUN cd /opt/ml/code && node golden-scenes/assemble.cjs seastate --out /tmp/smoke.cdn.html \
    && python -c "import sys; sys.path[:0]=['pipeline/harness','golden-scenes']; import harness, layer_harness; print('harness+layer_harness OK')"
