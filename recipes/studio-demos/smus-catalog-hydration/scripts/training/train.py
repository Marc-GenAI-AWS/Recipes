"""SageMaker Training Job entry point: trains the retail line-total regressor."""
import argparse
import os
from io import StringIO

import boto3
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

FEATURES = ["quantity", "unit_price", "country", "product_sku"]
TARGET = "line_total"


def load_csv(path: str) -> pd.DataFrame:
    if path.startswith("s3://"):
        s3 = boto3.client("s3")
        bucket, key = path[5:].split("/", 1)
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode()
        return pd.read_csv(StringIO(body))
    # SageMaker channel mode: directory of CSVs
    if os.path.isdir(path):
        files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".csv")]
        return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    return pd.read_csv(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    parser.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    parser.add_argument("--test-size", type=float, default=0.3)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    df = load_csv(args.train)
    print(f"Loaded {len(df)} rows, columns={list(df.columns)}")

    X = df[FEATURES]
    y = df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.random_state
    )

    pre = ColumnTransformer(
        transformers=[("cat", OneHotEncoder(handle_unknown="ignore"), ["country", "product_sku"])],
        remainder="passthrough",
    )
    pipe = Pipeline([("pre", pre), ("model", LinearRegression())])
    pipe.fit(X_train, y_train)

    preds = pipe.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    # SageMaker scrapes these regex patterns from the CloudWatch log into job metrics.
    print(f"validation:mae={mae:.6f};")
    print(f"validation:r2={r2:.6f};")

    os.makedirs(args.model_dir, exist_ok=True)
    joblib.dump(pipe, os.path.join(args.model_dir, "model.joblib"))
    print(f"Saved model to {args.model_dir}/model.joblib")


if __name__ == "__main__":
    main()
