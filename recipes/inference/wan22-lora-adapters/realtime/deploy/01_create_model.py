"""Register the SageMaker Model.

The inference code (inference.py, lora_cache.py, requirements.txt) lives inside
the base model prefix under `code/`, so it lands at /opt/ml/model/code/ in the
container. The PyTorch DLC's TorchServe entrypoint auto-imports
/opt/ml/model/code/{SAGEMAKER_PROGRAM} and pip-installs code/requirements.txt.
"""

import pathlib
import subprocess

import boto3

import config

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent / "code"


def upload_code() -> None:
    """Sync code/ into the model prefix so it mounts at /opt/ml/model/code/."""
    dest = config.BASE_MODEL_S3_URI.rstrip("/") + "/code/"
    print(f"Uploading {CODE_DIR} -> {dest}")
    subprocess.run(
        ["aws", "s3", "sync", str(CODE_DIR), dest,
         "--region", config.REGION, "--delete", "--exclude", "__pycache__/*"],
        check=True,
    )


def main() -> None:
    upload_code()
    sm = boto3.client("sagemaker", region_name=config.REGION)
    resp = sm.create_model(
        ModelName=config.MODEL_NAME,
        ExecutionRoleArn=config.ROLE_ARN,
        PrimaryContainer={
            "Image": config.INFERENCE_IMAGE_URI,
            "ModelDataSource": {
                "S3DataSource": {
                    "S3Uri": config.BASE_MODEL_S3_URI,
                    "S3DataType": "S3Prefix",
                    "CompressionType": "None",
                }
            },
            "Environment": {
                "SAGEMAKER_PROGRAM": "inference.py",
                "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                "SAGEMAKER_REGION": config.REGION,
                "OUTPUT_BUCKET": config.BUCKET,
                "OUTPUT_PREFIX": config.OUTPUT_PREFIX,
                # Generation defaults for the shared handler. inference.py is
                # byte-identical with the async sibling project; the defaults are
                # per-endpoint and live here. 25 frames / 10 steps is the largest
                # measured combination that fits the 60s real-time cap with headroom
                # (~30s warm on ml.g6e.8xlarge). The async fork injects 49/30.
                "DEFAULT_FRAMES": "25",
                "DEFAULT_STEPS": "10",
                # Real-time invocation is hard-capped at 60s by SageMaker regardless
                # of this value, so it will almost never bind. Kept generous so the
                # worker is not the thing that gives up first, which would otherwise
                # look like a container crash rather than a timeout.
                "TS_DEFAULT_RESPONSE_TIMEOUT": "3600",
                # TorchServe otherwise spawns one worker per GPU, and each would
                # load its own ~24GB copy of the pipeline.
                "SAGEMAKER_MODEL_SERVER_WORKERS": "1",
            },
        },
    )
    print("Model created:", resp["ModelArn"])


if __name__ == "__main__":
    main()
