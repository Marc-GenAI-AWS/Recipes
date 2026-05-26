"""Step 8: Launch a SageMaker Training Job using the SKLearn estimator.

Why a real training job: SMUS attributes the model to the project (via tags +
project-bucket artifact path), enabling the 'Register model' / 'Deploy' actions
on the Training Jobs page in the SMUS portal.

Requires PROJECT_EXECUTION_ROLE in your .env -- the role named
datazone_usr_role_<projectId>_<envId> on the Tooling environment.
"""
import sys

import boto3
from sagemaker import Session
from sagemaker.inputs import TrainingInput
from sagemaker.sklearn.estimator import SKLearn

from smus_demo.config import load_config


def main() -> int:
    cfg = load_config()
    if not cfg.project_execution_role:
        print("PROJECT_EXECUTION_ROLE is not set. See .env.example.", file=sys.stderr)
        return 1

    project_prefix = (
        f"dzd_{cfg.domain_id.split('_', 1)[-1]}/{cfg.project_id}/dev/data/ml/retail-line-total"
    )
    training_data = f"s3://{cfg.project_bucket}/{project_prefix}/input/"

    session = Session(boto_session=boto3.Session(region_name=cfg.region))

    estimator = SKLearn(
        entry_point="train.py",
        source_dir="scripts/training",
        role=cfg.project_execution_role,
        framework_version="1.2-1",
        py_version="py3",
        instance_type="ml.m5.large",
        instance_count=1,
        output_path=f"s3://{cfg.project_bucket}/{project_prefix}/output/",
        code_location=f"s3://{cfg.project_bucket}/{project_prefix}/source/",
        base_job_name="retail-line-total",
        hyperparameters={"test-size": 0.3, "random-state": 42},
        metric_definitions=[
            {"Name": "validation:mae", "Regex": r"validation:mae=([0-9\.]+);"},
            {"Name": "validation:r2",  "Regex": r"validation:r2=(-?[0-9\.]+);"},
        ],
        tags=[
            {"Key": "AmazonDataZoneDomain", "Value": cfg.domain_id},
            {"Key": "AmazonDataZoneProject", "Value": cfg.project_id},
        ],
        sagemaker_session=session,
    )
    estimator.fit({"train": TrainingInput(training_data, content_type="text/csv")}, wait=True)

    print("\nTraining job:", estimator.latest_training_job.name)
    print("Model artifact:", estimator.model_data)
    print("\nNext: open SMUS portal -> SMUS-Demo -> Training Jobs -> Register model -> Deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
