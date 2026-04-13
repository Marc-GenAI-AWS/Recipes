"""
Central configuration for cross-az-fsx-sagemaker.

All user-facing parameters live here, driven by environment variables.
Source your .env file before running any script:

    source .env          # bash/zsh
    # or: direnv, dotenv, etc.

This module is imported by the CDK app (infrastructure/app.py), the training
job launcher (launch_bionemo_job.py), and the data-prep scripts
(data_preparation/*.py).  A single .env change propagates everywhere.

Quick reference — variables you must set:
    AWS_REGION          AWS region for all resources      (default: us-west-2)
    FSX_AZ              AZ that holds the Lustre FS       (default: us-west-2a)
    SAGEMAKER_AZ        AZ that runs training jobs        (default: us-west-2c)
    BIONEMO_IMAGE       ECR URI of the BioNeMo container  (required)

See .env.example for the full list with explanations.
"""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("config")

# ── AWS ────────────────────────────────────────────────────────────────────────

REGION: str = os.environ.get("AWS_REGION", "us-west-2")

# Availability zone where the FSx Lustre filesystem is created.
# Your genomic data lives here; the filesystem is pinned to a single AZ.
FSX_AZ: str = os.environ.get("FSX_AZ", "us-west-2a")

# Availability zone where SageMaker training jobs run.
# Set this to a DIFFERENT AZ than FSX_AZ to exercise cross-AZ reads — that
# is the entire point of the architecture.  Same-AZ still works but defeats
# the validation.
SAGEMAKER_AZ: str = os.environ.get("SAGEMAKER_AZ", "us-west-2c")

# ── Network ────────────────────────────────────────────────────────────────────

VPC_CIDR: str = os.environ.get("VPC_CIDR", "10.0.0.0/16")

# ── FSx Lustre ─────────────────────────────────────────────────────────────────

# Filesystem size in GiB.
#   SCRATCH_2 minimum: 1200 GiB  (validation / ephemeral)
#   PERSISTENT_2 minimum: 1200 GiB  (production / durable)
# Scale in increments of 1200 GiB (e.g. 2400, 4800, 9600).
LUSTRE_STORAGE_GB: int = int(os.environ.get("LUSTRE_STORAGE_GB", "1200"))

# Deployment type: SCRATCH_2 (ephemeral, cheapest) or PERSISTENT_2 (durable,
# for production workloads that need the data to survive filesystem deletion).
LUSTRE_DEPLOYMENT_TYPE: str = os.environ.get("LUSTRE_DEPLOYMENT_TYPE", "SCRATCH_2")

# ── BioNeMo container ──────────────────────────────────────────────────────────

# Full ECR URI of your mirrored BioNeMo container.
# Format: <account_id>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>
# See README.md -> "Mirror the BioNeMo container to your ECR".
BIONEMO_IMAGE: str = os.environ.get(
    "BIONEMO_IMAGE",
    "<YOUR_ACCOUNT>.dkr.ecr.us-west-2.amazonaws.com/bionemo-framework:2.7.1",
)

# ── CDK stack names ────────────────────────────────────────────────────────────
# Override these to run multiple isolated stacks side-by-side
# (e.g. separate dev / staging / prod deployments in the same account).

NETWORK_STACK: str = os.environ.get("NETWORK_STACK", "CrossAzFsxNetwork")
IAM_STACK: str = os.environ.get("IAM_STACK", "CrossAzFsxIam")
LUSTRE_STACK: str = os.environ.get("LUSTRE_STACK", "CrossAzFsxLustre")


# ── Validation ─────────────────────────────────────────────────────────────────

def validate(require_bionemo_image: bool = True) -> None:
    """
    Check for obvious misconfiguration and exit with a clear message rather
    than letting a downstream boto3 call fail with a cryptic error.

    Call this at the top of each entry-point script:

        import config
        config.validate()

    Args:
        require_bionemo_image: set False for scripts that don't need the
            container image (e.g. pure CDK deploy steps).
    """
    errors: list[str] = []

    if require_bionemo_image and "<YOUR_ACCOUNT>" in BIONEMO_IMAGE:
        errors.append(
            "BIONEMO_IMAGE is not set.\n"
            "  Add it to your .env file:\n"
            f"    export BIONEMO_IMAGE=<account>.dkr.ecr.{REGION}.amazonaws.com/bionemo-framework:2.7.1\n"
            "  See README.md -> 'Mirror the BioNeMo container to your ECR'."
        )

    if not FSX_AZ.startswith(REGION):
        errors.append(
            f"FSX_AZ={FSX_AZ!r} is not in region {REGION!r}.\n"
            "  Check AWS_REGION and FSX_AZ in your .env file."
        )

    if not SAGEMAKER_AZ.startswith(REGION):
        errors.append(
            f"SAGEMAKER_AZ={SAGEMAKER_AZ!r} is not in region {REGION!r}.\n"
            "  Check AWS_REGION and SAGEMAKER_AZ in your .env file."
        )

    if LUSTRE_DEPLOYMENT_TYPE not in ("SCRATCH_2", "PERSISTENT_2"):
        errors.append(
            f"LUSTRE_DEPLOYMENT_TYPE={LUSTRE_DEPLOYMENT_TYPE!r} is not valid.\n"
            "  Valid values: SCRATCH_2, PERSISTENT_2"
        )

    if LUSTRE_STORAGE_GB < 1200 or LUSTRE_STORAGE_GB % 1200 != 0:
        errors.append(
            f"LUSTRE_STORAGE_GB={LUSTRE_STORAGE_GB} is invalid.\n"
            "  Must be a multiple of 1200 (e.g. 1200, 2400, 4800)."
        )

    if errors:
        for e in errors:
            print(f"[config] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Warn (don't fail) if both AZs are the same — it works but isn't cross-AZ.
    if FSX_AZ == SAGEMAKER_AZ:
        log.warning(
            "FSX_AZ and SAGEMAKER_AZ are both %s — training will NOT cross AZ boundaries. "
            "Set SAGEMAKER_AZ to a different AZ to exercise the cross-AZ design.",
            FSX_AZ,
        )


def summary() -> str:
    """Return a human-readable config summary for logging at startup."""
    return (
        f"  region:                {REGION}\n"
        f"  fsx_az:                {FSX_AZ}\n"
        f"  sagemaker_az:          {SAGEMAKER_AZ}\n"
        f"  cross_az:              {FSX_AZ != SAGEMAKER_AZ}\n"
        f"  vpc_cidr:              {VPC_CIDR}\n"
        f"  lustre_storage_gb:     {LUSTRE_STORAGE_GB}\n"
        f"  lustre_deployment:     {LUSTRE_DEPLOYMENT_TYPE}\n"
        f"  bionemo_image:         {BIONEMO_IMAGE}\n"
        f"  network_stack:         {NETWORK_STACK}\n"
        f"  iam_stack:             {IAM_STACK}\n"
        f"  lustre_stack:          {LUSTRE_STACK}"
    )
