#!/usr/bin/env python3
"""
Launch a SageMaker training job that runs BioNeMo Evo2 fine-tuning against
cross-AZ FSx for Lustre.

Uses SageMaker's native FSx for Lustre FileSystemConfig support:
  - FSx Lustre lives in FSX_AZ (set in .env, e.g. us-west-2a)
  - Training job runs in SAGEMAKER_AZ (set in .env, e.g. us-west-2c)
  - Training container sees Lustre mounted at /opt/ml/input/data/<channel>/
  - Reads during training traverse the cross-AZ boundary — that's the whole
    point of the validation.

All parameters are sourced from .env via config.py.  Run `source .env` first.
"""

import argparse
import base64
import logging
import sys
from pathlib import Path

import boto3
import config
import training_job_config as tjc

REGION = config.REGION
NETWORK_STACK = config.NETWORK_STACK
IAM_STACK = config.IAM_STACK
LUSTRE_STACK = config.LUSTRE_STACK
BIONEMO_IMAGE = config.BIONEMO_IMAGE
LUSTRE_CHANNEL_NAME = "training"

log = logging.getLogger("launch_bionemo_job")


def stack_outputs(cf, stack_name: str) -> dict[str, str]:
    return {o["OutputKey"]: o["OutputValue"]
            for o in cf.describe_stacks(StackName=stack_name)["Stacks"][0].get("Outputs", [])}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Launch a SageMaker BioNeMo Evo2 training job against cross-AZ FSx Lustre. "
            "Defaults are read from training_job_config.py; CLI flags override for one-off changes."
        )
    )
    parser.add_argument("--job-name", required=True,
                        help="Unique SageMaker training job name")
    # ── Data ──
    parser.add_argument("--phase-subdir", default=tjc.PHASE_SUBDIR,
                        help="Lustre subdir holding training data (default: %(default)s)")
    parser.add_argument("--preproc-prefix", default=tjc.PREPROC_PREFIX,
                        help="Preprocessed .bin/.idx filename prefix (default: %(default)s)")
    parser.add_argument("--ckpt-subdir", default=tjc.CKPT_SUBDIR,
                        help="Lustre subdir with NeMo2 checkpoint; empty = train from scratch")
    parser.add_argument("--ckpt-s3-uri", default=tjc.CKPT_S3_URI,
                        help="S3 URI of an existing checkpoint (e.g. s3://bucket/path/). "
                             "Downloaded into the container at job start via aws s3 sync. "
                             "Takes precedence over --ckpt-subdir if both are set.")
    # ── Model ──
    parser.add_argument("--model-size", default=tjc.MODEL_SIZE,
                        help="Evo2 model variant (default: %(default)s)")
    # ── Compute ──
    parser.add_argument("--instance-type", default=tjc.INSTANCE_TYPE,
                        help="SageMaker instance type (default: %(default)s)")
    parser.add_argument("--devices", type=int, default=tjc.DEVICES,
                        help="Number of GPUs on the instance (default: %(default)s)")
    # ── Parallelism ──
    parser.add_argument("--tensor-parallel", type=int, default=tjc.TENSOR_PARALLEL,
                        help="Tensor parallelism degree (default: %(default)s)")
    parser.add_argument("--pipeline-parallel", type=int, default=tjc.PIPELINE_PARALLEL,
                        help="Pipeline parallelism degree (default: %(default)s)")
    parser.add_argument("--activation-ckpt-layers", type=int, default=tjc.ACTIVATION_CKPT_LAYERS,
                        help="Gradient checkpointing layers (default: %(default)s)")
    # ── Hyperparameters ──
    parser.add_argument("--micro-batch-size", type=int, default=tjc.MICRO_BATCH_SIZE,
                        help="Micro-batch size per GPU (default: %(default)s)")
    parser.add_argument("--seq-length", type=int, default=tjc.SEQ_LENGTH,
                        help="Sequence length in tokens (default: %(default)s)")
    parser.add_argument("--max-steps", type=int, default=tjc.MAX_STEPS,
                        help="Number of optimiser steps (default: %(default)s)")
    # ── Job limits ──
    parser.add_argument("--max-runtime-seconds", type=int, default=tjc.MAX_RUNTIME_SECONDS,
                        help="SageMaker hard stop timeout in seconds (default: %(default)s)")
    parser.add_argument("--lustre-access-mode", default=tjc.LUSTRE_ACCESS_MODE,
                        choices=["ro", "rw"],
                        help="Lustre filesystem access mode (default: %(default)s)")
    # ── Misc ──
    parser.add_argument("--subnet-override", default=None,
                        help="Override SageMaker subnet ID (e.g. to target a specific AZ)")
    parser.add_argument("--cuda-launch-blocking", type=int, default=tjc.CUDA_LAUNCH_BLOCKING,
                        help="Set CUDA_LAUNCH_BLOCKING=1 for synchronous error reporting")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the training job definition JSON without submitting")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config.validate()
    tjc.validate()
    log.info("Infrastructure config:\n%s", config.summary())
    log.info("Training job config:\n%s", tjc.summary())

    session = boto3.Session(region_name=REGION)
    cf = session.client("cloudformation")
    sm = session.client("sagemaker")
    sts = session.client("sts")
    s3 = session.client("s3")
    account_id = sts.get_caller_identity()["Account"]

    net = stack_outputs(cf, NETWORK_STACK)
    iam = stack_outputs(cf, IAM_STACK)
    lustre = stack_outputs(cf, LUSTRE_STACK)

    sagemaker_subnet_id = args.subnet_override or net["SageMakerSubnetId"]
    sagemaker_sg_id = net["SageMakerSecurityGroupId"]
    role_arn = iam["SageMakerExecutionRoleArn"]
    lustre_fs_id = lustre["LustreFileSystemId"]
    lustre_mount_name = lustre["LustreMountName"]

    fsx_subnet_id = net["FsxSubnetId"]
    subnets = session.client("ec2").describe_subnets(
        SubnetIds=[fsx_subnet_id, sagemaker_subnet_id]
    )["Subnets"]
    az_by_subnet = {s["SubnetId"]: s["AvailabilityZone"] for s in subnets}
    fsx_az = az_by_subnet[fsx_subnet_id]
    training_az = az_by_subnet[sagemaker_subnet_id]

    log.info("  job name:           %s", args.job_name)
    log.info("  image:              %s", BIONEMO_IMAGE)
    log.info("  instance type:      %s", args.instance_type)
    log.info("  sm subnet:          %s (%s)", sagemaker_subnet_id, training_az)
    log.info("  sm sg:              %s", sagemaker_sg_id)
    log.info("  lustre fs id:       %s", lustre_fs_id)
    log.info("  lustre mount name:  %s", lustre_mount_name)
    log.info("  fsx az:             %s", fsx_az)
    log.info("  cross-az:           %s", fsx_az != training_az)
    log.info("  phase subdir:       %s", args.phase_subdir)
    log.info("  ckpt subdir:        %s", args.ckpt_subdir)
    log.info("  preproc prefix:     %s", args.preproc_prefix)
    log.info("  model size:         %s", args.model_size)
    log.info("  max steps:          %s", args.max_steps)

    # Upload entrypoint script so SageMaker can stage it into the container
    bucket = f"sagemaker-{REGION}-{account_id}"
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        log.info("Creating SageMaker default bucket %s", bucket)
        s3.create_bucket(Bucket=bucket,
                         CreateBucketConfiguration={"LocationConstraint": REGION})
    entrypoint_path = Path(__file__).parent / "training_container" / "bionemo_entrypoint.sh"
    code_key = f"bionemo-code/{args.job_name}/bionemo_entrypoint.sh"
    log.info("Uploading entrypoint to s3://%s/%s", bucket, code_key)
    s3.put_object(Bucket=bucket, Key=code_key, Body=entrypoint_path.read_bytes())

    env = {
        "LUSTRE_CHANNEL": LUSTRE_CHANNEL_NAME,
        "PHASE_SUBDIR": args.phase_subdir,
        "CKPT_SUBDIR": args.ckpt_subdir,
        "CKPT_S3_URI": args.ckpt_s3_uri,
        "PREPROC_PREFIX": args.preproc_prefix,
        "MODEL_SIZE": args.model_size,
        "MAX_STEPS": str(args.max_steps),
        "MICRO_BATCH_SIZE": str(args.micro_batch_size),
        "SEQ_LENGTH": str(args.seq_length),
        "DEVICES": str(args.devices),
        "TENSOR_PARALLEL": str(args.tensor_parallel),
        "PIPELINE_PARALLEL": str(args.pipeline_parallel),
        "ACTIVATION_CKPT_LAYERS": str(args.activation_ckpt_layers),
        "CUDA_LAUNCH_BLOCKING": str(getattr(args, 'cuda_launch_blocking', 0)),
        "FSX_AZ": fsx_az,
        "TRAINING_AZ": training_az,
    }

    training_job = {
        "TrainingJobName": args.job_name,
        "RoleArn": role_arn,
        "AlgorithmSpecification": {
            "TrainingImage": BIONEMO_IMAGE,
            "TrainingInputMode": "File",
            "ContainerEntrypoint": ["/bin/bash"],
            "ContainerArguments": ["/opt/ml/input/data/code/bionemo_entrypoint.sh"],
        },
        "InputDataConfig": [
            {
                # SageMaker mounts Lustre natively here.
                # DirectoryPath is the path WITHIN the Lustre filesystem.
                # SageMaker's Lustre mount maps this to /opt/ml/input/data/<channel>/.
                "ChannelName": LUSTRE_CHANNEL_NAME,
                "DataSource": {
                    "FileSystemDataSource": {
                        "FileSystemId": lustre_fs_id,
                        "FileSystemType": "FSxLustre",
                        "DirectoryPath": f"/{lustre_mount_name}",
                        "FileSystemAccessMode": args.lustre_access_mode,
                    }
                },
                "InputMode": "File",
            },
            {
                "ChannelName": "code",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket}/bionemo-code/{args.job_name}/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "application/octet-stream",
                "InputMode": "File",
            },
        ],
        "OutputDataConfig": {
            "S3OutputPath": f"s3://{bucket}/bionemo-validation/",
        },
        "ResourceConfig": {
            "InstanceType": args.instance_type,
            "InstanceCount": 1,
            "VolumeSizeInGB": tjc.INSTANCE_VOLUME_GB,
        },
        "StoppingCondition": {
            "MaxRuntimeInSeconds": args.max_runtime_seconds,
        },
        "VpcConfig": {
            "SecurityGroupIds": [sagemaker_sg_id],
            "Subnets": [sagemaker_subnet_id],
        },
        "Environment": env,
        "EnableNetworkIsolation": False,
        "Tags": [
            {"Key": "Project", "Value": "cross-az-fsx-validation"},
            {"Key": "Phase", "Value": args.phase_subdir},
        ],
    }

    if args.dry_run:
        import json
        print(json.dumps(training_job, indent=2, default=str))
        return 0

    log.info("Creating training job %s", args.job_name)
    resp = sm.create_training_job(**training_job)
    log.info("TrainingJobArn: %s", resp["TrainingJobArn"])
    log.info("Monitor: aws sagemaker describe-training-job --region %s --training-job-name %s",
             REGION, args.job_name)
    log.info("Logs:    aws logs tail /aws/sagemaker/TrainingJobs --region %s --follow --log-stream-name-prefix %s",
             REGION, args.job_name)
    print(args.job_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
