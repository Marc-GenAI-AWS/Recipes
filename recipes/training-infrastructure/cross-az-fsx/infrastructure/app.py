#!/usr/bin/env python3
"""
AWS CDK app for cross-AZ FSx for Lustre + SageMaker Training Jobs.

Deploys three stacks:
  - Network:  VPC, subnets in FSX_AZ and SAGEMAKER_AZ, security groups,
              S3 gateway endpoint
  - IAM:      SageMaker execution role + EC2 data-prep role
  - Lustre:   FSx for Lustre filesystem in FSX_AZ

All parameters are driven by environment variables defined in .env.
Run `source .env` before `cdk deploy`.

See config.py (one level up) for the full parameter reference.
"""
import sys
from pathlib import Path

# config.py lives one directory above infrastructure/ (at the repo root).
# Insert that directory onto the path so we can import it here.
sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

import aws_cdk as cdk  # noqa: E402
from stacks.network_stack import NetworkStack  # noqa: E402
from stacks.iam_stack import IamStack  # noqa: E402
from stacks.lustre_stack import LustreStack  # noqa: E402

# Validate config before synthesising — catches missing BIONEMO_IMAGE etc.
# Pass require_bionemo_image=False here because CDK deploy doesn't need the
# container URI; only the training job launcher does.
config.validate(require_bionemo_image=False)

print("Deploying with config:")
print(config.summary())

app = cdk.App()
env = cdk.Environment(region=config.REGION)

network_stack = NetworkStack(
    app,
    config.NETWORK_STACK,
    fsx_az=config.FSX_AZ,
    sagemaker_az=config.SAGEMAKER_AZ,
    vpc_cidr=config.VPC_CIDR,
    env=env,
    description=(
        f"VPC and networking for cross-AZ FSx Lustre + SageMaker "
        f"(FSx in {config.FSX_AZ}, training in {config.SAGEMAKER_AZ})"
    ),
)

iam_stack = IamStack(
    app,
    config.IAM_STACK,
    env=env,
    description="IAM roles for SageMaker Training Jobs and EC2 data-prep instances",
)

lustre_stack = LustreStack(
    app,
    config.LUSTRE_STACK,
    vpc=network_stack.vpc,
    fsx_subnet=network_stack.fsx_subnet,
    sagemaker_security_group=network_stack.sagemaker_security_group,
    ec2_data_prep_security_group=network_stack.ec2_data_prep_security_group,
    storage_capacity_gb=config.LUSTRE_STORAGE_GB,
    deployment_type=config.LUSTRE_DEPLOYMENT_TYPE,
    env=env,
    description=(
        f"FSx for Lustre ({config.LUSTRE_DEPLOYMENT_TYPE}, "
        f"{config.LUSTRE_STORAGE_GB} GiB, v2.15) in {config.FSX_AZ}"
    ),
)
lustre_stack.add_dependency(network_stack)

app.synth()
