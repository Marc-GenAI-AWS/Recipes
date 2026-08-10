"""Create the endpoint and wait for it to be InService."""

import time

import boto3

import config


def main() -> None:
    sm = boto3.client("sagemaker", region_name=config.REGION)
    sm.create_endpoint(
        EndpointName=config.ENDPOINT_NAME,
        EndpointConfigName=config.ENDPOINT_CONFIG_NAME,
    )
    print(f"Endpoint {config.ENDPOINT_NAME} creating...")

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

    print(f"Endpoint {config.ENDPOINT_NAME} is InService.")


if __name__ == "__main__":
    main()
