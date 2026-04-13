#!/bin/bash
# End-to-end scaling test: deploys infra, stages data, runs the 1B baseline
# training job. Expected wall clock: ~90 minutes (10 min infra + 60 min data
# prep including image pull + 20 min training).
#
# Prerequisites:
#   - CDK bootstrapped in target account/region
#   - BIONEMO_IMAGE env var set to your ECR URI
#   - SageMaker quotas requested for ml.g5.12xlarge
#
# Usage:
#   export BIONEMO_IMAGE=<your-ecr-uri>
#   ./examples/run_scaling_test.sh

set -euxo pipefail

if [ -z "${BIONEMO_IMAGE:-}" ]; then
    echo "ERROR: set BIONEMO_IMAGE env var to your ECR URI"
    echo "  export BIONEMO_IMAGE=123456789012.dkr.ecr.us-west-2.amazonaws.com/bionemo-framework:2.7.1"
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Step 1: Deploy infrastructure ==="
cd infrastructure
if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/cdk deploy --all --require-approval never
cd ..

echo ""
echo "=== Step 2: Stage training data ==="
cd data_preparation
PREP_INSTANCE=$(../infrastructure/.venv/bin/python scale_data_on_lustre.py \
    --phase-subdir phase_10gb \
    --target-raw-gb 13 \
    --output-prefix hg38_10gb \
    | tail -1)
echo "Launched prep instance: $PREP_INSTANCE"
echo "Waiting for it to complete..."
aws ec2 wait instance-terminated --instance-ids "$PREP_INSTANCE"
echo "Data staging complete."
cd ..

echo ""
echo "=== Step 3: Launch SageMaker training job ==="
JOB_NAME="bionemo-1b-10gb-$(date +%Y%m%d-%H%M%S)"
infrastructure/.venv/bin/python launch_bionemo_job.py \
    --job-name "$JOB_NAME" \
    --phase-subdir phase_10gb \
    --preproc-prefix hg38_10gb \
    --model-size 1b_nv \
    --instance-type ml.g5.12xlarge \
    --max-steps 10 \
    --micro-batch-size 1 \
    --seq-length 8192 \
    --devices 4 \
    --tensor-parallel 1 \
    --pipeline-parallel 4 \
    --activation-ckpt-layers 5 \
    --max-runtime-seconds 5400

echo ""
echo "=== Job launched: $JOB_NAME ==="
echo "Monitor with:"
echo "  aws sagemaker describe-training-job --training-job-name $JOB_NAME"
echo "  aws logs tail /aws/sagemaker/TrainingJobs --follow --log-stream-name-prefix $JOB_NAME"
