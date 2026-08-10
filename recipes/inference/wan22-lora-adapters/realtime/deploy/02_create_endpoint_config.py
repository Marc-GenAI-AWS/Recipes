"""Create the SageMaker EndpointConfig for a *real-time* inference endpoint.

Absence of `AsyncInferenceConfig` here is the whole difference vs the async sibling
project: the endpoint returns the response inline on `invoke_endpoint` instead of
writing it to S3.

The tradeoff:

    Real-time invocation is hard-capped at 60 seconds. SageMaker returns
    ModelError / ReadTimeout after that regardless of what the container does.

That budget is enough for short generations on a warm worker (measured ~30s at 25
frames / 10 steps on ml.g6e.8xlarge). 01_create_model.py injects exactly those
values as the container defaults, and `04_invoke.py` sends the same ones; larger
requests are accepted per-payload but risk overrunning the cap. See the README for
the safe request-size envelope.

If longer generations are needed, the async project remains the right tool -- this
one exists for interactive, short, "generate now and hand me the URL" use.
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
    )
    print("EndpointConfig created:", resp["EndpointConfigArn"])


if __name__ == "__main__":
    main()
