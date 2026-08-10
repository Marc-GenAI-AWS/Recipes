"""Shared configuration for the deploy scripts. Edit values here in one place.

===========================================================================
CUSTOMER SETUP -- three fields must be set before the first deploy.
Everything else has sensible defaults.

  1. REGION       -- AWS region where the endpoint runs
  2. BUCKET       -- S3 bucket holding the base model + LoRAs + outputs
  3. ROLE_ARN     -- SageMaker execution role with SageMaker + S3 permissions

If REGION is not us-west-2, INFERENCE_IMAGE_URI must also be updated -- the DLC
image is region-scoped. See its comment block below.
===========================================================================
"""

# ------------------------------------------------------------------ region
# All resources -- endpoint, S3 bucket, ECR image -- must be in the same
# region. Cross-region model artifact reads are not supported by SageMaker.
REGION = "us-west-2"

# --------------------------------------------------------------- S3 bucket
# Replace with your own bucket name; every other S3 URI in this file derives
# from it. Bucket must live in REGION above.
#
# Required contents before first deploy:
#   s3://{BUCKET}/wan2.2-ti2v-5b-diffusers/   Wan-AI/Wan2.2-TI2V-5B-Diffusers
#   s3://{BUCKET}/loras/<name>/               At least one adapter, or pass --no-adapter
#
# `generations/` is created on first write and does not need to pre-exist.
# Run `preflight.py` after populating to verify layout before deploying.
BUCKET = "amzn-s3-demo-bucket"

# ------------------------------------------------- SageMaker execution role
# ARN of the IAM role SageMaker assumes when running the endpoint. The role
# must trust `sagemaker.amazonaws.com` and grant:
#   - sagemaker: full access (AmazonSageMakerFullAccess is the easy path)
#   - s3:GetObject on s3://{BUCKET}/*
#   - s3:PutObject on s3://{BUCKET}/{OUTPUT_PREFIX}/*
#   - logs:CreateLogStream / logs:PutLogEvents on the endpoint's log group
# Format: arn:aws:iam::<account-id>:role/<role-name>
ROLE_ARN = "arn:aws:iam::111122223333:role/YourSageMakerExecutionRole"

# ================================================================
# Below this line: defaults that usually do not need to change.
# ================================================================

# Diffusers-format base model. The original Wan-AI research layout (Wan2.2_VAE.pth,
# models_t5_umt5-xxl-enc-bf16.pth, ...) does NOT load with WanPipeline.from_pretrained --
# it has no model_index.json. This prefix holds Wan-AI/Wan2.2-TI2V-5B-Diffusers.
BASE_MODEL_S3_URI = f"s3://{BUCKET}/wan2.2-ti2v-5b-diffusers/"

# Adapters live outside the model artifact so a new LoRA needs no redeploy.
LORA_PREFIX = f"s3://{BUCKET}/loras/"
DEFAULT_ADAPTER_S3_URI = f"{LORA_PREFIX}hstoric-color/"

OUTPUT_PREFIX = "generations"

# SageMaker naming (immutable once created -- bump the version suffix to redeploy).
# Distinct from the async project's names so both endpoints can coexist.
MODEL_NAME = "wan22-ti2v-5b-rt-v1"
ENDPOINT_CONFIG_NAME = "wan22-ti2v-5b-rt-cfg-v1"
ENDPOINT_NAME = "wan22-ti2v-5b-realtime"

# 1x L40S 48GB. Resident footprint is ~24GB (transformer bf16 ~10GB +
# UMT5-XXL bf16 ~11GB + VAE fp32 ~3GB), leaving headroom for activations at 720p.
# Requires a service-quota grant for this instance type in REGION.
INSTANCE_TYPE = "ml.g6e.8xlarge"
INITIAL_INSTANCE_COUNT = 1

# PyTorch inference DLC. This image URI is REGION-SCOPED -- the account ID prefix
# (763104351884) and the ".us-west-2." segment both change per region. If you
# change REGION above, look up the matching image URI at:
#   https://github.com/aws/deep-learning-containers/blob/master/available_images.md
# The rest of the tag (pytorch-inference:2.6.0-gpu-py312-...) is the version we
# validated against and should not change without re-testing.
INFERENCE_IMAGE_URI = (
    "763104351884.dkr.ecr.us-west-2.amazonaws.com/"
    "pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker-v1.84-2026-06-15-19-03-30"
)
