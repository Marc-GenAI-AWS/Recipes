#!/usr/bin/env python3
"""
Hydrate an FSx Lustre filesystem with genomic training data.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHAT DOES THIS SCRIPT DO?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  This script populates an empty FSx Lustre filesystem with the genomic
  training data that Evo2 needs.  You run it once per data scale (phase)
  before launching a training job.

  It works by spinning up a temporary EC2 instance that:
    1. Mounts the FSx Lustre filesystem
    2. Downloads the human reference genome (hg38) from UCSC (~3 GB per copy)
    3. Replicates it as many times as needed to reach the target data size
    4. Runs preprocess_evo2 inside the BioNeMo container to convert the raw
       FASTA files into the .bin/.idx format that Evo2 reads during training
    5. Writes everything to Lustre so the training job can access it
    6. Shuts itself down automatically when finished

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DOES IT REGENERATE THE DATA EVERY TIME I RUN IT?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  No.  The script is safe to re-run.  Before copying any files, it checks
  how many bytes are already in the phase directory on Lustre.  If the data
  is already there and meets the target size, it skips the copy step.

  The preprocessing step (preprocess_evo2) always runs — this is intentional
  because it's fast compared to the data copy and ensures the .bin/.idx files
  are complete and consistent with whatever raw data is present.  The config
  includes "overwrite: true" so it replaces any partial previous run cleanly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOW DO I KNOW WHEN IT'S DONE?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  The script prints an EC2 instance ID when it launches.  Monitor it with:

      # Stream logs in real time
      aws ssm start-session --target <instance-id> --region us-west-2

      # Or wait silently until the instance terminates (it shuts itself down)
      aws ec2 wait instance-terminated --instance-ids <instance-id> --region us-west-2

  When the instance disappears from your EC2 console, the data is on Lustre
  and ready for training.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOW TO USE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Standard usage — pick a phase and let the presets handle everything:

      python data_preparation/scale_data_on_lustre.py --phase phase_10gb
      python data_preparation/scale_data_on_lustre.py --phase phase_100gb
      python data_preparation/scale_data_on_lustre.py --phase phase_500gb
      python data_preparation/scale_data_on_lustre.py --phase phase_1tb

  All phase definitions (target size, file prefix, EC2 instance) live in
  training_job_config.py.  That is the single source of truth — if the name
  or prefix ever changes, it changes in one place and both the data script
  and the training launcher stay in sync automatically.

  Preview what the script will do without actually launching anything:

      python data_preparation/scale_data_on_lustre.py --phase phase_100gb --dry-run

  Override individual settings for a one-off experiment:

      python data_preparation/scale_data_on_lustre.py \\
          --phase phase_100gb \\
          --target-raw-gb 75 \\
          --output-prefix hg38_custom_75gb
"""

import argparse
import logging
import sys
from pathlib import Path

import _ec2_launcher_common as common

# training_job_config.py lives one directory above data_preparation/ (repo root).
# We import it here so phase definitions stay in one place — this script
# reads the same PHASES table that launch_bionemo_job.py uses, ensuring
# the data path and file prefix are always in sync with the training job.
sys.path.insert(0, str(Path(__file__).parent.parent))
import training_job_config as tjc

REGION = common.REGION
LUSTRE_STACK = common.LUSTRE_STACK

log = logging.getLogger("scale_data_on_lustre")

# ── Preprocessing config ────────────────────────────────────────────────────────
#
# This YAML is passed to preprocess_evo2 inside the BioNeMo container.
# "Relaxed" filters are used deliberately — the goal is to maximise the
# volume of preprocessed data for bandwidth testing, not to apply the strict
# quality filters you would use for a production training run.
#
# Key settings explained:
#   embed_reverse_complement: true  — generates both strands, doubling output size
#   drop_empty_sequences: false     — keeps sequences with no valid bases (adds volume)
#   nnn_filter: false               — keeps N-regions (unassembled genome gaps)
#   overwrite: true                 — replaces any existing .bin/.idx from a prior run
#
# If you want production-quality preprocessing instead, change these three
# booleans to: embed_reverse_complement: false, drop_empty_sequences: true,
# nnn_filter: true.  Output will be ~20x smaller but biologically cleaner.

PREPROCESS_YAML = """\
- datapaths: DATAPATHS_PLACEHOLDER
  output_dir: "OUTPUT_DIR_PLACEHOLDER"
  output_prefix: OUTPUT_PREFIX_PLACEHOLDER
  train_split: 0.98
  valid_split: 0.01
  test_split: 0.01
  overwrite: true
  embed_reverse_complement: true
  random_reverse_complement: 0.0
  random_lineage_dropout: 0.0
  transcribe: "back_transcribe"
  force_uppercase: true
  indexed_dataset_dtype: "uint8"
  append_eod: true
  enforce_sample_length: null
  ftfy: false
  tokenizer_type: "Byte-Level"
  vocab_file: null
  vocab_size: null
  merges_file: null
  tokenizer_model_name: null
  pretrained_tokenizer_model: null
  special_tokens: null
  fast_hf_tokenizer: true
  workers: 2
  preproc_concurrency: 100
  chunksize: 1
  drop_empty_sequences: false
  nnn_filter: false
  seed: 42
"""


def build_userdata(lustre_dns: str, lustre_mount_name: str,
                   phase_subdir: str, target_raw_gb: int, output_prefix: str,
                   bionemo_image: str) -> str:
    """
    Build the EC2 userdata shell script that runs on the temporary instance.

    This script is what actually does the work — it runs as root on the EC2
    instance at first boot and carries out all five steps described in the
    module docstring above.  The instance self-terminates at the end.
    """
    config_body = (
        PREPROCESS_YAML
        .replace("DATAPATHS_PLACEHOLDER", "DATAPATHS_SHELL_EXPANSION")
        .replace("OUTPUT_DIR_PLACEHOLDER", f"/mnt/lustre/{phase_subdir}/preprocessed")
        .replace("OUTPUT_PREFIX_PLACEHOLDER", output_prefix)
    )

    return f"""#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EC2 userdata — FSx Lustre data hydration
# Phase:  {phase_subdir}  |  Target: {target_raw_gb} GB raw  |  Prefix: {output_prefix}
#
# This script runs automatically at instance launch.  Do not run it manually.
# Monitor progress via SSM Session Manager or CloudWatch Logs.
# The instance terminates itself when the script finishes.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
exec > >(tee -a /var/log/scale_data.log) 2>&1
set -x
trap 'ec=$?; echo "=== FAILED (exit=$ec) at line $LINENO — check /var/log/scale_data.log ==="; exit $ec' ERR
set -eo pipefail

echo "=== Data hydration started $(date -u +%FT%TZ) ==="
echo "    Phase:   {phase_subdir}"
echo "    Target:  {target_raw_gb} GB raw FASTA"
echo "    Prefix:  {output_prefix}"

# ── STEP 1: Install the FSx Lustre client ────────────────────────────────────
#
# The DLAMI (Deep Learning AMI) ships with Docker and NVIDIA drivers but not
# the Lustre client.  We install it from the Amazon FSx repo, which provides
# a version guaranteed to work with Lustre 2.15 servers (the default in our
# CDK stack).  The kernel module version must match the running kernel — if
# the exact match isn't available, we fall back to the generic aws package.

apt-get update -y
apt-get install -y --no-install-recommends curl wget gnupg

if ! command -v mount.lustre >/dev/null 2>&1; then
    echo "--- Installing FSx Lustre client ---"
    wget -O - https://fsx-lustre-client-repo-public-keys.s3.amazonaws.com/fsx-ubuntu-public-key.asc \
        | gpg --dearmor | tee /usr/share/keyrings/fsx-ubuntu-public-key.gpg >/dev/null
    echo "deb [signed-by=/usr/share/keyrings/fsx-ubuntu-public-key.gpg] https://fsx-lustre-client-repo.s3.amazonaws.com/ubuntu jammy main" \
        | tee /etc/apt/sources.list.d/fsxlustreclientrepo.list
    apt-get update -y
    # Try exact kernel version first; fall back to generic aws package
    apt-get install -y --no-install-recommends lustre-client-modules-$(uname -r) || \
    apt-get install -y --no-install-recommends lustre-client-modules-aws
fi
command -v mount.lustre && mount.lustre --version || echo "WARN: mount.lustre still missing after install"

# ── STEP 2: Mount the FSx Lustre filesystem ──────────────────────────────────
#
# We mount Lustre at /mnt/lustre.  The DNS name and mount name come from the
# CDK stack outputs — they were resolved by the Python launcher and injected
# into this script at launch time.
#
# relatime  — updates access timestamps only when the file was modified more
#             recently than the last access, reducing metadata traffic.
# flock     — enables POSIX file locking, required by some training frameworks.

mkdir -p /mnt/lustre
mount -t lustre -o relatime,flock \
    {lustre_dns}@tcp:/{lustre_mount_name} /mnt/lustre
echo "=== Lustre mounted at /mnt/lustre ==="
ls /mnt/lustre/

PHASE_DIR=/mnt/lustre/{phase_subdir}
PREPROC_DIR=$PHASE_DIR/preprocessed
mkdir -p "$PHASE_DIR" "$PREPROC_DIR"

# ── STEP 3: Populate raw FASTA files ─────────────────────────────────────────
#
# We use the human reference genome (hg38) as the source data.  It's publicly
# available from UCSC, freely licensed, and at ~3 GB per copy it's a good
# unit for replication.
#
# IDEMPOTENCY: We check how many bytes already exist in the phase directory.
# If the directory already meets the target size, we skip all copying.  This
# means it's safe to re-run this script — it will not download or copy
# anything if the data is already there.
#
# If the directory is partially populated (e.g. from a previous interrupted
# run), we calculate exactly how many additional copies are needed and add
# only those.

STAGE_DIR=/var/tmp/fsx-stage
mkdir -p $STAGE_DIR
HG38_GZ=$STAGE_DIR/hg38.fa.gz
HG38_FA=$STAGE_DIR/hg38.fa

# Download hg38 if not already on local disk (the instance's EBS volume, not Lustre)
if [ ! -f "$HG38_GZ" ]; then
    echo "--- Downloading hg38.fa.gz from UCSC (~3 GB, takes a few minutes) ---"
    curl -sSL https://hgdownload.soe.ucsc.edu/goldenpath/hg38/bigZips/hg38.fa.gz -o "$HG38_GZ"
fi
if [ ! -f "$HG38_FA" ]; then
    echo "--- Decompressing hg38.fa.gz ---"
    gunzip -k -f "$HG38_GZ"
fi

PER_COPY=$(stat -c %s "$HG38_FA")
TARGET_BYTES=$(( {target_raw_gb} * 1000 * 1000 * 1000 ))

# Count what's already on Lustre for this phase
EXISTING=$(find $PHASE_DIR -maxdepth 1 -name 'hg38_*.fa' 2>/dev/null | wc -l || echo 0)
START_EXISTING_BYTES=$(find $PHASE_DIR -maxdepth 1 -name 'hg38_*.fa' -printf '%s\n' 2>/dev/null | awk '{{sum+=$1}} END {{print sum+0}}')
echo "Phase dir currently has $EXISTING FASTA files totalling $START_EXISTING_BYTES bytes"
echo "Target: $TARGET_BYTES bytes ({target_raw_gb} GB)"

NEEDED=$(( TARGET_BYTES - START_EXISTING_BYTES ))
if [ "$NEEDED" -le 0 ]; then
    # Data already meets the target — nothing to copy
    echo "=== Phase dir already meets target size — skipping FASTA copy ==="
else
    COPIES=$(( (NEEDED + PER_COPY - 1) / PER_COPY ))
    echo "--- Copying $COPIES more genome files ($NEEDED bytes needed) ---"
    START_IDX=$EXISTING
    for i in $(seq 1 $COPIES); do
        IDX=$(( START_IDX + i - 1 ))
        DEST=$PHASE_DIR/hg38_$(printf '%04d' $IDX).fa
        echo "Writing $DEST"
        cp "$HG38_FA" "$DEST"
    done
fi

echo "--- Phase dir contents after copy ---"
du -sh "$PHASE_DIR"
find $PHASE_DIR -maxdepth 1 -name 'hg38_*.fa' | sort | head -5
echo "..."
find $PHASE_DIR -maxdepth 1 -name 'hg38_*.fa' | sort | tail -5

# ── STEP 4: Preprocess the FASTA files into .bin/.idx format ─────────────────
#
# Evo2 does not read raw FASTA files during training.  It reads a binary
# indexed format (.bin + .idx) produced by preprocess_evo2.  This step
# converts all the FASTA copies in the phase directory into that format.
#
# We run preprocess_evo2 inside the BioNeMo container (the same container
# the training job uses) so the output format is guaranteed to be compatible.
#
# The output goes to $PHASE_DIR/preprocessed/ with filenames like:
#   hg38_10gb_train.bin  /  hg38_10gb_train.idx
#   hg38_10gb_valid.bin  /  hg38_10gb_valid.idx
#   hg38_10gb_test.bin   /  hg38_10gb_test.idx
#
# These are the files the training job looks for.  The prefix (hg38_10gb)
# must match PREPROC_PREFIX in training_job_config.py — which it does
# because both are derived from the same PHASES table.
#
# "overwrite: true" in the config means re-running this step is always safe.

CONFIG=$PHASE_DIR/preprocess_config_relaxed.yaml

# Build the list of all FASTA files to include
FASTA_FILES=$(find $PHASE_DIR -maxdepth 1 -name 'hg38_*.fa' | sort)
DATAPATHS_ARR="["
for f in $FASTA_FILES; do
    DATAPATHS_ARR="$DATAPATHS_ARR\\"$f\\","
done
DATAPATHS_ARR="${{DATAPATHS_ARR%,}}]"

cat > "$CONFIG" <<PREPROC_EOF
{config_body}
PREPROC_EOF
sed -i "s#DATAPATHS_SHELL_EXPANSION#$DATAPATHS_ARR#" "$CONFIG"

echo "--- Preprocessing config written to $CONFIG ---"
cat "$CONFIG"

# Log in to ECR so Docker can pull the BioNeMo image
ECR_REGION={REGION}
ECR_REGISTRY=$(echo "{bionemo_image}" | cut -d/ -f1)
aws ecr get-login-password --region $ECR_REGION \
    | docker login --username AWS --password-stdin $ECR_REGISTRY

# Remove pre-loaded DLAMI images to free disk space for the BioNeMo pull
docker image prune -af || true

echo "--- Pulling BioNeMo container ---"
docker pull {bionemo_image}

echo "--- Running preprocess_evo2 (this is the longest step) ---"
docker run --rm --gpus all \
    --network host \
    --name bionemo-preprocess \
    -v /mnt/lustre:/mnt/lustre \
    -w /workspace/bionemo2 \
    --entrypoint bash \
    {bionemo_image} \
    -c "preprocess_evo2 -c $CONFIG"

echo "=== Preprocessing complete ==="
echo "--- Output files in $PREPROC_DIR ---"
du -sh $PREPROC_DIR
ls -lh $PREPROC_DIR

# ── STEP 5: Clean up and self-terminate ───────────────────────────────────────
#
# Unmount Lustre cleanly, then terminate this EC2 instance.
# Self-termination is intentional — the instance has no other purpose and
# leaving it running would incur unnecessary cost.  The IAM role attached to
# this instance allows it to terminate only itself (scoped by the Project tag).

umount /mnt/lustre || true

echo "=== Data hydration complete $(date -u +%FT%TZ) ==="
echo "    Phase {phase_subdir} is ready on Lustre."
echo "    Set ACTIVE_PHASE = '{phase_subdir}' in training_job_config.py"
echo "    then run: python launch_bionemo_job.py --job-name <name>"
echo ""
echo "=== Self-terminating EC2 instance ==="
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
INSTANCE_ID=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --region {REGION} --instance-ids "$INSTANCE_ID"
"""


def main() -> int:
    valid_phases = list(tjc.PHASES.keys())

    parser = argparse.ArgumentParser(
        description=(
            "Hydrate an FSx Lustre filesystem with genomic training data. "
            "Downloads hg38 from UCSC, replicates to the target size, and "
            "runs preprocess_evo2 — all starting from a completely empty "
            f"filesystem.  Phase presets: {valid_phases}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            f"  {name:15s}  {p['description']}"
            f"  (target={p['target_raw_gb']} GB, instance={p['data_instance']})"
            for name, p in tjc.PHASES.items()
        ),
    )

    parser.add_argument(
        "--phase",
        choices=valid_phases,
        required=True,
        help="Data phase to generate (see phase table above)",
    )

    # Optional overrides — use for one-off experiments without editing the config.
    parser.add_argument("--target-raw-gb", type=int, default=None,
                        help="Override raw FASTA GB target for this run only")
    parser.add_argument("--output-prefix", default=None,
                        help="Override preprocessed file prefix for this run only")
    parser.add_argument("--instance-type", default=None,
                        help="Override EC2 instance type for this run only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the EC2 userdata script without launching anything")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Validate infrastructure config (region, AZs, image URI, etc.)
    import config
    config.validate()

    # Resolve effective values: CLI override takes precedence over phase preset.
    phase = tjc.PHASES[args.phase]
    target_raw_gb = args.target_raw_gb or phase["target_raw_gb"]
    output_prefix = args.output_prefix or phase["preproc_prefix"]
    instance_type = args.instance_type or phase["data_instance"]
    phase_subdir  = args.phase

    log.info("Data hydration job:")
    log.info("  phase:            %s", args.phase)
    log.info("  description:      %s", phase["description"])
    log.info("  target raw GB:    %s", target_raw_gb)
    log.info("  output prefix:    %s", output_prefix)
    log.info("  instance type:    %s", instance_type)
    log.info("  BioNeMo image:    %s", common.BIONEMO_IMAGE)

    # Resolve infrastructure (VPC, Lustre, IAM) from CDK stack outputs
    ctx = common.PrepEc2Context()
    log.info("Resolved infra:")
    ctx.log_summary()

    user_data = build_userdata(
        lustre_dns=ctx.lustre_dns,
        lustre_mount_name=ctx.lustre_mount_name,
        phase_subdir=phase_subdir,
        target_raw_gb=target_raw_gb,
        output_prefix=output_prefix,
        bionemo_image=common.BIONEMO_IMAGE,
    )

    if args.dry_run:
        print(user_data)
        return 0

    instance_id = ctx.run_instances(
        instance_type=instance_type,
        user_data=user_data,
        name_tag=f"hydrate-{phase_subdir}",
        extra_tags={"Purpose": "data-hydration", "Phase": phase_subdir},
        volume_size_gb=300,  # Local EBS for hg38 download staging; Lustre holds final data
    )

    log.info("EC2 instance launched: %s", instance_id)
    log.info("The instance will self-terminate when hydration is complete.")
    log.info("")
    log.info("Monitor live:  aws ssm start-session --target %s --region %s",
             instance_id, REGION)
    log.info("Wait for done: aws ec2 wait instance-terminated"
             " --instance-ids %s --region %s", instance_id, REGION)
    log.info("")
    log.info("When complete, set ACTIVE_PHASE = %r in training_job_config.py", phase_subdir)
    log.info("then run: python launch_bionemo_job.py --job-name <your-job-name>")

    print(instance_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
