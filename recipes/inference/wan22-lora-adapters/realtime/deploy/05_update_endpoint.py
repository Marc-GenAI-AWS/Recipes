"""Blue/green swap the running endpoint to a new Model + EndpointConfig.

Names for the Model and EndpointConfig are immutable in SageMaker, so any
change requires new names (bumped in config.py). This script creates the new
Model + EndpointConfig if missing, calls update_endpoint, and polls until
InService.
"""

import subprocess
import sys
import time

import boto3

import config


def main() -> None:
    sm = boto3.client("sagemaker", region_name=config.REGION)

    try:
        sm.describe_model(ModelName=config.MODEL_NAME)
        print(f"Model {config.MODEL_NAME} already exists, skipping create")
    except sm.exceptions.ClientError:
        subprocess.run([sys.executable, "01_create_model.py"], check=True)

    try:
        sm.describe_endpoint_config(EndpointConfigName=config.ENDPOINT_CONFIG_NAME)
        print(f"EndpointConfig {config.ENDPOINT_CONFIG_NAME} already exists, skipping create")
    except sm.exceptions.ClientError:
        subprocess.run([sys.executable, "02_create_endpoint_config.py"], check=True)

    sm.update_endpoint(
        EndpointName=config.ENDPOINT_NAME,
        EndpointConfigName=config.ENDPOINT_CONFIG_NAME,
    )
    print(f"update_endpoint dispatched -> {config.ENDPOINT_CONFIG_NAME}")

    while True:
        desc = sm.describe_endpoint(EndpointName=config.ENDPOINT_NAME)
        status = desc["EndpointStatus"]
        print(f"  status={status}")
        if status in ("InService", "Failed"):
            if status == "Failed":
                print("FailureReason:", desc.get("FailureReason"))
                raise SystemExit(1)
            break
        time.sleep(30)

    print("Endpoint updated and InService.")


if __name__ == "__main__":
    main()
