"""SageMaker SKLearn inference handler for the retail line-total regressor."""
import json
import os
from io import StringIO

import joblib
import pandas as pd

FEATURES = ["quantity", "unit_price", "country", "product_sku"]


def model_fn(model_dir):
    return joblib.load(os.path.join(model_dir, "model.joblib"))


def input_fn(request_body, content_type):
    if content_type == "application/json":
        payload = json.loads(request_body)
        if isinstance(payload, dict) and "instances" in payload:
            payload = payload["instances"]
        return pd.DataFrame(payload, columns=FEATURES)
    if content_type == "text/csv":
        return pd.read_csv(StringIO(request_body), header=None, names=FEATURES)
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(data, model):
    return model.predict(data)


def output_fn(prediction, accept):
    if accept == "text/csv":
        return ",".join(f"{v:.4f}" for v in prediction), "text/csv"
    return json.dumps({"predictions": [float(v) for v in prediction]}), "application/json"
