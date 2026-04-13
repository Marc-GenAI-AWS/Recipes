#!/usr/bin/env python3
"""Launch a tiny throwaway t3.small that mounts FSx, walks the tree, prints
contents to CloudWatch via SSM, then self-terminates. Used for post-prep sanity
checks without launching a full GPU instance."""

import sys
import _ec2_launcher_common as common


BODY = """
mkdir -p /mnt/fsx
mount -t nfs -o nfsvers=4.1 FSX_DNS_PLACEHOLDER:JUNCTION_PLACEHOLDER /mnt/fsx

echo "=== /mnt/fsx tree ==="
find /mnt/fsx -maxdepth 4 -printf "%y %s %p\\n" 2>&1 | sort | head -200

echo "=== phase_10gb/preprocessed ==="
ls -la /mnt/fsx/phase_10gb/preprocessed/ 2>&1

echo "=== checkpoints ==="
ls -la /mnt/fsx/checkpoints/ 2>&1
find /mnt/fsx/checkpoints -maxdepth 3 -printf "%p %s\\n" 2>&1 | sort

echo "=== du ==="
du -sh /mnt/fsx/phase_10gb /mnt/fsx/checkpoints 2>&1
"""

# Build custom userdata that skips the docker/ecr/pull preamble entirely since
# t3.small has no GPU and we don't need docker at all.
USERDATA_LIGHT_TEMPLATE = """#!/bin/bash
exec > >(tee -a /var/log/fsx_check.log) 2>&1
set -x
echo "=== userdata start $(date -u +%FT%TZ) ==="
dnf install -y nfs-utils
mkdir -p /mnt/fsx
mount -t nfs -o nfsvers=4.1 {svm_dns}:JUNCTION_PLACEHOLDER /mnt/fsx
echo "=== mounted, SSM in and explore /mnt/fsx ==="
""".replace("JUNCTION_PLACEHOLDER", common.FSX_JUNCTION)


def main() -> int:
    ctx = common.PrepEc2Context()
    # Override DLAMI with AL2023 to get a small root volume
    al2023_ami = ctx.ssm.get_parameter(
        Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    )["Parameter"]["Value"]
    ctx.ami_id = al2023_ami

    user_data = USERDATA_LIGHT_TEMPLATE.replace("{svm_dns}", ctx.svm_dns)
    instance_id = ctx.run_instances(
        instance_type="t3.small",
        user_data=user_data,
        name_tag="fsx-check",
        extra_tags={"Purpose": "fsx-check"},
        volume_size_gb=8,
    )
    print(instance_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
