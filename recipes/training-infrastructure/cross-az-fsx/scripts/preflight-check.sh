#!/bin/bash
# Pre-flight check: validates that everything is set up correctly before
# deploying infrastructure or running training jobs. Exits non-zero on any
# missing or misconfigured item so you can script around it.
#
# Usage:
#   ./scripts/preflight-check.sh
#
# Checks:
#   1. Required CLI tools installed (aws, docker, cdk, python3, node)
#   2. AWS credentials are present and working
#   3. NGC login is valid (~/.docker/config.json has nvcr.io entry)
#   4. BIONEMO_IMAGE env var is set and the repo exists in ECR
#   5. Python 3.10+ available
#   6. Node 18+ available

set -u  # treat unset vars as errors
FAILED=0
ok() { echo "  [OK]   $*"; }
warn() { echo "  [WARN] $*"; }
fail() { echo "  [FAIL] $*"; FAILED=$((FAILED + 1)); }
section() { echo ""; echo "== $* =="; }

section "CLI tools"
for tool in aws docker python3 node cdk; do
    if command -v "$tool" >/dev/null 2>&1; then
        version=$("$tool" --version 2>&1 | head -1)
        ok "$tool installed: $version"
    else
        fail "$tool not found in PATH"
    fi
done

section "Python version (need 3.10+)"
if command -v python3 >/dev/null 2>&1; then
    py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    py_major=$(echo "$py_version" | cut -d. -f1)
    py_minor=$(echo "$py_version" | cut -d. -f2)
    if [ "$py_major" -ge 3 ] && [ "$py_minor" -ge 10 ]; then
        ok "Python $py_version"
    else
        fail "Python $py_version is too old (need 3.10+)"
    fi
fi

section "Node version (need 18+ for CDK)"
if command -v node >/dev/null 2>&1; then
    node_version=$(node --version | sed 's/^v//')
    node_major=$(echo "$node_version" | cut -d. -f1)
    if [ "$node_major" -ge 18 ]; then
        ok "Node $node_version"
    else
        fail "Node $node_version is too old (need 18+)"
    fi
fi

section "AWS credentials"
if aws sts get-caller-identity >/dev/null 2>&1; then
    account_id=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    arn=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)
    ok "AWS credentials valid"
    ok "  Account ID: $account_id"
    ok "  Identity:   $arn"
else
    fail "AWS credentials missing or expired"
    fail "  Run: aws configure, or set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY"
fi

section "AWS region"
region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [ -z "$region" ]; then
    # Try to read from AWS config
    region=$(aws configure get region 2>/dev/null || true)
fi
if [ -n "$region" ]; then
    ok "Region: $region"
else
    fail "AWS_REGION not set and no default in ~/.aws/config"
    fail "  Run: export AWS_REGION=us-west-2"
fi

section "NGC docker login (~/.docker/config.json)"
if [ -f "$HOME/.docker/config.json" ]; then
    if python3 -c "
import json, sys
cfg = json.load(open('$HOME/.docker/config.json'))
auths = cfg.get('auths', {})
if 'nvcr.io' in auths and auths['nvcr.io'].get('auth'):
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        ok "nvcr.io credentials present in ~/.docker/config.json"
    else
        fail "Not logged in to nvcr.io"
        fail "  Run: docker login nvcr.io (username: \$oauthtoken, password: your NGC API key)"
        fail "  See README.md -> 'Credentials setup' -> 'Step 1: NVIDIA NGC API key'"
    fi
else
    fail "~/.docker/config.json does not exist"
    fail "  Docker is installed but you've never logged in. Run:"
    fail "    docker login nvcr.io"
fi

section "BIONEMO_IMAGE env var"
if [ -z "${BIONEMO_IMAGE:-}" ]; then
    fail "BIONEMO_IMAGE not set"
    fail "  Run: export BIONEMO_IMAGE=\$AWS_ACCOUNT_ID.dkr.ecr.\$AWS_REGION.amazonaws.com/bionemo-framework:2.7.1"
    fail "  Or: source .env  (after copying .env.example -> .env)"
elif [[ "$BIONEMO_IMAGE" == *"<YOUR_ACCOUNT>"* ]]; then
    fail "BIONEMO_IMAGE still contains the placeholder '<YOUR_ACCOUNT>'"
    fail "  Replace with your real account ID"
else
    ok "BIONEMO_IMAGE=$BIONEMO_IMAGE"

    # Verify the ECR repo exists
    repo_name=$(echo "$BIONEMO_IMAGE" | sed 's|^[^/]*/||' | cut -d: -f1)
    if [ -n "${region}" ]; then
        if aws ecr describe-repositories --repository-names "$repo_name" --region "$region" >/dev/null 2>&1; then
            ok "ECR repository '$repo_name' exists"

            # Check if any image is pushed
            image_count=$(aws ecr describe-images --repository-name "$repo_name" --region "$region" --query 'length(imageDetails)' --output text 2>/dev/null || echo 0)
            if [ "$image_count" != "0" ]; then
                ok "ECR repository has $image_count image(s)"
            else
                warn "ECR repository exists but has no images yet"
                warn "  You still need to pull from nvcr.io and push to ECR"
                warn "  See README.md -> 'Credentials setup' -> 'Step 3'"
            fi
        else
            fail "ECR repository '$repo_name' does not exist in region $region"
            fail "  Run: aws ecr create-repository --repository-name $repo_name --region $region"
        fi
    fi
fi

section "CDK bootstrap status"
if [ -n "${region:-}" ] && aws sts get-caller-identity >/dev/null 2>&1; then
    if aws cloudformation describe-stacks --stack-name CDKToolkit --region "$region" >/dev/null 2>&1; then
        ok "CDK is bootstrapped in $region"
    else
        warn "CDK not bootstrapped in $region (needed before first 'cdk deploy')"
        warn "  Run: cdk bootstrap aws://\$AWS_ACCOUNT_ID/$region"
    fi
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "================================"
    echo "  All pre-flight checks passed."
    echo "================================"
    exit 0
else
    echo "================================"
    echo "  $FAILED check(s) failed."
    echo "  Fix the items above, then re-run this script."
    echo "================================"
    exit 1
fi
