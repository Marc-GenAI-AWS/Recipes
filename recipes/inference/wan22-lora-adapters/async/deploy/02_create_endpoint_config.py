"""Create the SageMaker EndpointConfig for *async* inference.

Async inference is the managed fit for this workload: generation runs for minutes and
produces a large artifact. SageMaker queues the request, invokes the container
normally, and writes the response to S3 -- so the handler stays a plain
request/response function with no custom streaming code, and the 60-second real-time
invocation cap does not apply.
"""

import boto3

import config


def main() -> None:
    sm = boto3.client("sagemaker", region_name=config.REGION)
    resp = sm.create_endpoint_config(
        EndpointConfigName=config.ENDPOINT_CONFIG_NAME,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": config.MODEL_NAME,
                "InstanceType": config.INSTANCE_TYPE,
                "InitialInstanceCount": config.INITIAL_INSTANCE_COUNT,
                # 34GB artifact download + pipeline load to GPU.
                "ContainerStartupHealthCheckTimeoutInSeconds": 1800,
                "ModelDataDownloadTimeoutInSeconds": 1800,
            }
        ],
        AsyncInferenceConfig={
            "OutputConfig": {
                "S3OutputPath": config.ASYNC_OUTPUT_PATH,
                "S3FailurePath": config.ASYNC_ERROR_PATH,
            },
            "ClientConfig": {
                # One generation at a time per instance -- the GPU is saturated by a
                # single request, so queueing beyond this only adds latency.
                "MaxConcurrentInvocationsPerInstance": 1
            },
        },
    )
    print("EndpointConfig created:", resp["EndpointConfigArn"])


if __name__ == "__main__":
    main()
