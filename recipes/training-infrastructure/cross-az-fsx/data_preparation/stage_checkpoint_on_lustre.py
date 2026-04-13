#!/usr/bin/env python3
"""
Download a pretrained Evo2 checkpoint from NGC and stage it on FSx Lustre.

Launches a throwaway EC2 instance in the FSx subnet that:
  1. Installs the Amazon FSx Lustre client
  2. Mounts the FSx Lustre filesystem
  3. Pulls the BioNeMo container image from your ECR mirror
  4. Runs `download_bionemo_data <resource>` inside the container with your
     NGC API key, which downloads the checkpoint into the container's cache
  5. Copies the checkpoint out of the container into /mnt/lustre/checkpoints/
  6. Self-terminates

The resulting checkpoint at /mnt/lustre/checkpoints/<dest_subdir>/ is ready
to be passed to launch_bionemo_job.py via --ckpt-subdir for fine-tuning.

Security: the NGC API key is read from ~/.docker/config.json (where
`docker login nvcr.io` stores it) and injected into the EC2 userdata in
plaintext. Userdata is visible to anyone with ec2:DescribeInstanceAttribute
in your account. Consider using AWS Secrets Manager for production.

Usage:
    python stage_checkpoint_on_lustre.py \\
        --resource evo2/1b-8k-bf16:1.0 \\
        --dest-subdir evo2_1b_8k_bf16
"""

import argparse
import logging
import sys

import _ec2_launcher_common as common

REGION = common.REGION
LUSTRE_STACK = common.LUSTRE_STACK

log = logging.getLogger("stage_checkpoint_on_lustre")


def build_userdata(lustre_dns: str, lustre_mount_name: str,
                   resource: str, dest_subdir: str,
                   ngc_api_key: str, bionemo_image: str) -> str:
    """EC2 userdata that mounts Lustre, pulls BioNeMo image, runs
    download_bionemo_data inside the container, and copies the result to
    Lustre."""
    return f"""#!/bin/bash
exec > >(tee -a /var/log/stage_checkpoint.log) 2>&1
set -x
trap 'ec=$?; echo "=== userdata FAILED (exit=$ec) at line $LINENO ==="; exit $ec' ERR
set -eo pipefail

echo "=== start $(date -u +%FT%TZ) ==="

# DLAMI is Ubuntu 22.04 - install the Amazon FSx Lustre client
apt-get update -y
apt-get install -y --no-install-recommends curl wget gnupg rsync
if ! command -v mount.lustre >/dev/null 2>&1; then
    wget -O - https://fsx-lustre-client-repo-public-keys.s3.amazonaws.com/fsx-ubuntu-public-key.asc \\
        | gpg --dearmor | tee /usr/share/keyrings/fsx-ubuntu-public-key.gpg >/dev/null
    echo "deb [signed-by=/usr/share/keyrings/fsx-ubuntu-public-key.gpg] https://fsx-lustre-client-repo.s3.amazonaws.com/ubuntu jammy main" \\
        | tee /etc/apt/sources.list.d/fsxlustreclientrepo.list
    apt-get update -y
    apt-get install -y --no-install-recommends lustre-client-modules-$(uname -r) || \\
    apt-get install -y --no-install-recommends lustre-client-modules-aws
fi

# Mount FSx Lustre
mkdir -p /mnt/lustre
mount -t lustre -o relatime,flock \\
    {lustre_dns}@tcp:/{lustre_mount_name} /mnt/lustre
echo "=== Lustre mounted ==="
mkdir -p /mnt/lustre/checkpoints

# Prune DLAMI preloaded images to reclaim disk for the BioNeMo pull
docker image prune -af || true

# ECR login and pull the BioNeMo container
ECR_REGISTRY=$(echo "{bionemo_image}" | cut -d/ -f1)
aws ecr get-login-password --region {REGION} \\
    | docker login --username AWS --password-stdin $ECR_REGISTRY
docker pull {bionemo_image}

# Download the checkpoint inside the container.
# download_bionemo_data reads the NGC key from ~/.ngc/config inside the
# container. We inject it via the -e NGC_API_KEY env var and have a tiny
# shim create the config file at runtime.
DEST=/mnt/lustre/checkpoints/{dest_subdir}
mkdir -p "$DEST"

docker run --rm --gpus all \\
    --network host \\
    --name bionemo-stage-ckpt \\
    -v /mnt/lustre:/mnt/lustre \\
    -e NGC_API_KEY='{ngc_api_key}' \\
    -e BIONEMO_DATA_SOURCE=/mnt/lustre/checkpoints/.bionemo-cache \\
    --entrypoint bash \\
    {bionemo_image} -c '
set -euxo pipefail

# Set up ~/.ngc/config inside the container so download_bionemo_data finds it
mkdir -p /root/.ngc
cat > /root/.ngc/config <<NGC_EOF
[CURRENT]
apikey = $NGC_API_KEY
format_type = json
NGC_EOF
chmod 600 /root/.ngc/config

mkdir -p /mnt/lustre/checkpoints/.bionemo-cache

# Download the resource. CLI returns the local path on stdout.
CKPT_PATH=$(download_bionemo_data {resource})
echo "Downloaded checkpoint to: $CKPT_PATH"
ls -la "$CKPT_PATH"

# Copy the checkpoint contents directly into the final destination
# (strips the intermediate cache directory structure)
rsync -a "$CKPT_PATH"/ /mnt/lustre/checkpoints/{dest_subdir}/

echo "=== staged checkpoint contents ==="
ls -la /mnt/lustre/checkpoints/{dest_subdir}/
du -sh /mnt/lustre/checkpoints/{dest_subdir}/
'

echo "=== checkpoint staging complete ==="
ls -la "$DEST"
du -sh "$DEST"

umount /mnt/lustre || true

echo "=== self-terminating ==="
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
INSTANCE_ID=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --region {REGION} --instance-ids "$INSTANCE_ID"
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource", default="evo2/1b-8k-bf16:1.0",
                        help="NGC resource name to pass to download_bionemo_data. "
                             "Examples: evo2/1b-8k-bf16:1.0, evo2/7b-1m:1.0, "
                             "evo2/40b-1m-fp8-bf16:1.0. Run "
                             "`download_bionemo_data --list-resources` inside "
                             "the container for the full catalog.")
    parser.add_argument("--dest-subdir", default="evo2_1b_8k_bf16",
                        help="Subdirectory under /mnt/lustre/checkpoints/ where "
                             "the checkpoint will be staged")
    parser.add_argument("--instance-type", default="g5.xlarge",
                        help="EC2 instance type (GPU required for NVIDIA container entrypoint)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import config; config.validate()

    # Read NGC key from docker config (set up via `docker login nvcr.io`)
    ngc_key = common.get_ngc_api_key_from_docker_config()
    if not ngc_key:
        log.error("NGC API key not found in ~/.docker/config.json")
        log.error("Run: docker login nvcr.io (username: $oauthtoken, password: your NGC API key)")
        log.error("See README.md -> 'Credentials setup' -> 'Step 1'")
        return 2

    ctx = common.PrepEc2Context()
    log.info("Resolved infra:")
    ctx.log_summary()
    log.info("  instance type:    %s", args.instance_type)
    log.info("  NGC resource:     %s", args.resource)
    log.info("  Lustre dest:      /mnt/lustre/checkpoints/%s", args.dest_subdir)
    log.info("  BioNeMo image:    %s", common.BIONEMO_IMAGE)

    user_data = build_userdata(
        lustre_dns=ctx.lustre_dns,
        lustre_mount_name=ctx.lustre_mount_name,
        resource=args.resource,
        dest_subdir=args.dest_subdir,
        ngc_api_key=ngc_key,
        bionemo_image=common.BIONEMO_IMAGE,
    )

    if args.dry_run:
        # Don't print the NGC key in dry-run output
        print(user_data.replace(ngc_key, "<REDACTED>"))
        return 0

    instance_id = ctx.run_instances(
        instance_type=args.instance_type,
        user_data=user_data,
        name_tag=f"stage-ckpt-{args.dest_subdir}",
        extra_tags={"Purpose": "stage-checkpoint", "Resource": args.resource},
        volume_size_gb=300,
    )
    log.info("Launched %s", instance_id)
    log.info("Monitor: aws ssm start-session --target %s --region %s",
             instance_id, REGION)
    log.info("Wait:    aws ec2 wait instance-terminated --instance-ids %s --region %s",
             instance_id, REGION)
    print(instance_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
