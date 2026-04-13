"""
Shared helpers for launching throwaway GPU EC2 instances that run the BioNeMo
container against FSx Lustre. Used by scale_data_on_lustre.py,
stage_checkpoint_on_lustre.py, and check_fsx_state.py.

All configuration is sourced from config.py (repo root) which reads from the
.env file.  Run `source .env` before invoking any data-prep script.
"""

from __future__ import annotations

import base64
import json
import logging
import sys
from pathlib import Path

import boto3

# config.py lives one directory above data_preparation/
sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

REGION = config.REGION
NETWORK_STACK = config.NETWORK_STACK
IAM_STACK = config.IAM_STACK
LUSTRE_STACK = config.LUSTRE_STACK
BIONEMO_IMAGE = config.BIONEMO_IMAGE
PROJECT_TAG = "cross-az-fsx-validation"

MAX_TTL_HOURS = 4

# DLAMI (Deep Learning Base OSS Nvidia Driver Ubuntu 22.04) ships with Docker +
# nvidia-container-toolkit + CUDA drivers, so we don't have to install any of it.
DLAMI_SSM_PARAMETER = (
    "/aws/service/deeplearning/ami/x86_64/"
    "base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id"
)

log = logging.getLogger("ec2_launcher_common")


def stack_outputs(cf, stack_name: str) -> dict[str, str]:
    resp = cf.describe_stacks(StackName=stack_name)
    return {o["OutputKey"]: o["OutputValue"]
            for o in resp["Stacks"][0].get("Outputs", [])}


def get_ngc_api_key_from_docker_config() -> str | None:
    """Pull the NGC API key out of ~/.docker/config.json if we logged in earlier."""
    cfg_path = Path.home() / ".docker" / "config.json"
    if not cfg_path.exists():
        return None
    try:
        cfg = json.loads(cfg_path.read_text())
    except json.JSONDecodeError:
        return None
    nvcr = cfg.get("auths", {}).get("nvcr.io", {})
    auth_b64 = nvcr.get("auth")
    if not auth_b64:
        return None
    try:
        decoded = base64.b64decode(auth_b64).decode("utf-8")
    except Exception:
        return None
    # Format is "username:password" — for NGC, username is literally "$oauthtoken"
    if ":" not in decoded:
        return None
    _, api_key = decoded.split(":", 1)
    return api_key if api_key.startswith("nvapi-") else None


class PrepEc2Context:
    """Resolves all infra dependencies in one shot."""

    def __init__(self):
        self.session = boto3.Session(region_name=REGION)
        cf = self.session.client("cloudformation")
        self.ec2 = self.session.client("ec2")
        self.ssm = self.session.client("ssm")
        self.fsx = self.session.client("fsx")

        net = stack_outputs(cf, NETWORK_STACK)
        iam = stack_outputs(cf, IAM_STACK)
        lustre = stack_outputs(cf, LUSTRE_STACK)
        self.subnet_id = net["FsxSubnetId"]
        self.security_group_id = net["Ec2DataPrepSecurityGroupId"]
        self.instance_profile = iam["Ec2DataPrepInstanceProfileName"]
        self.lustre_fs_id = lustre["LustreFileSystemId"]
        self.lustre_dns = lustre["LustreDnsName"]
        self.lustre_mount_name = lustre["LustreMountName"]
        self.ami_id = self.ssm.get_parameter(Name=DLAMI_SSM_PARAMETER)["Parameter"]["Value"]

    def log_summary(self) -> None:
        log.info("  subnet:             %s", self.subnet_id)
        log.info("  security group:     %s", self.security_group_id)
        log.info("  instance profile:   %s", self.instance_profile)
        log.info("  Lustre FS ID:       %s", self.lustre_fs_id)
        log.info("  Lustre DNS:         %s", self.lustre_dns)
        log.info("  Lustre mount name:  %s", self.lustre_mount_name)
        log.info("  AMI (DLAMI):        %s", self.ami_id)

    def run_instances(self, *, instance_type: str, user_data: str,
                      name_tag: str, extra_tags: dict[str, str] | None = None,
                      volume_size_gb: int = 300) -> str:
        tags = {
            "Name": name_tag,
            "Project": PROJECT_TAG,
            "AutoTerminate": "true",
            "MaxTtlHours": str(MAX_TTL_HOURS),
        }
        if extra_tags:
            tags.update(extra_tags)
        resp = self.ec2.run_instances(
            ImageId=self.ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            IamInstanceProfile={"Name": self.instance_profile},
            NetworkInterfaces=[{
                "DeviceIndex": 0,
                "SubnetId": self.subnet_id,
                "Groups": [self.security_group_id],
                "AssociatePublicIpAddress": True,
            }],
            UserData=user_data,
            BlockDeviceMappings=[{
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "VolumeSize": volume_size_gb,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True,
                },
            }],
            InstanceInitiatedShutdownBehavior="terminate",
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
            }],
        )
        return resp["Instances"][0]["InstanceId"]


# The individual scripts (scale_data_on_lustre.py, check_fsx_state.py) build
# their own user-data payloads directly because each has a different setup
# sequence. If you add a new prep script that shares the Lustre mount +
# ECR-pull pattern, factor the common bits into a helper here.
