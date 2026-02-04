"""
Launch an Evo2 SageMaker training job.
"""
import sagemaker
from sagemaker.estimator import Estimator


IMAGE_URI = "<YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<IMAGE>:<TAG>"
ROLE = None  # Will auto-detect
INSTANCE_TYPE = "ml.g5.12xlarge"
VOLUME_SIZE = 200
NUM_GPUS = 4
TRAIN_DATA_S3 = None

HYPERPARAMETERS = {
    "model-size": "1b",
    "max-steps": 10,
    "seq-length": 128,
    "micro-batch-size": 1,
    "global-batch-size": NUM_GPUS,
    "lr": 3e-4,
    "min-lr": 3e-5,
    "warmup-steps": 100,
    "weight-decay": 0.01,
    "num-nodes": 1,
    "devices": NUM_GPUS,
    "mock-data": "",
    "result-dir": "/opt/ml/model",
    "experiment-name": "evo2-sagemaker",
    "limit-val-batches": 2,
    "val-check-interval": 5,
    "disable-checkpointing": "",
    "log-every-n-steps": 1,
}

ENVIRONMENT = {
    "TRITON_LIBCUDA_PATH": "/usr/lib/x86_64-linux-gnu/libcuda.so.1",
}


def main():
    session = sagemaker.Session()
    print(f"Region: {session.boto_region_name}")
    print(f"Bucket: {session.default_bucket()}")
    
    role = ROLE or sagemaker.get_execution_role()
    print(f"Role: {role}")
    
    estimator = Estimator(
        image_uri=IMAGE_URI,
        role=role,
        instance_count=1,
        instance_type=INSTANCE_TYPE,
        volume_size=VOLUME_SIZE,
        output_path=f"s3://{session.default_bucket()}/evo2-output",
        sagemaker_session=session,
        source_dir="src/",
        entry_point="train.py",
        hyperparameters=HYPERPARAMETERS,
        environment=ENVIRONMENT,
        max_run=3600,
        container_entry_point=["python"],
    )
    
    print(f"\nLaunching Evo2 training on {INSTANCE_TYPE} with {NUM_GPUS} GPUs...")
    estimator.fit(None, wait=True)
    
    print(f"\nTraining complete!")
    print(f"Model artifacts: {estimator.model_data}")

if __name__ == '__main__':
    main()
