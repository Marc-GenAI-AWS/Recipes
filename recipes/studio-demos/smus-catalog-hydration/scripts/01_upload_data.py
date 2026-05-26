"""Step 1: Create the demo S3 bucket (if needed) and upload the retail CSVs.

Uploads to s3://${DEMO_BUCKET}/retail/<table>/<file>.csv and also stages
order_items_enriched.csv into the project's managed bucket so the SageMaker
training job in step 8 can read it under the project execution role.
"""
import sys
from pathlib import Path

import botocore

from smus_demo.config import load_config, s3_client

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TABLES = ["customers", "orders", "order_items", "order_items_enriched"]


def ensure_bucket(s3, bucket: str, region: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  Bucket {bucket} already exists")
        return
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
            raise
    print(f"  Creating bucket {bucket}")
    if region == "us-east-1":
        s3.create_bucket(Bucket=bucket)
    else:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": region},
        )


def main() -> int:
    cfg = load_config()
    s3 = s3_client(cfg)

    ensure_bucket(s3, cfg.demo_bucket, cfg.region)

    print(f"Uploading {len(TABLES)} CSVs to s3://{cfg.demo_bucket}/retail/")
    for table in TABLES:
        local = DATA_DIR / f"{table}.csv"
        if not local.exists():
            print(f"  ! missing {local}", file=sys.stderr)
            return 1
        key = f"retail/{table}/{table}.csv"
        s3.upload_file(str(local), cfg.demo_bucket, key)
        print(f"  uploaded s3://{cfg.demo_bucket}/{key}")

    # Stage training data into the project bucket so the project's execution
    # role can read it during the SageMaker Training Job (step 8).
    train_key = (
        f"dzd_{cfg.domain_id.split('_', 1)[-1]}/{cfg.project_id}"
        f"/dev/data/ml/retail-line-total/input/order_items_enriched.csv"
    )
    s3.upload_file(
        str(DATA_DIR / "order_items_enriched.csv"),
        cfg.project_bucket,
        train_key,
    )
    print(f"  staged training data at s3://{cfg.project_bucket}/{train_key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
