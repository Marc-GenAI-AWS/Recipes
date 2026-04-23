

import os
import argparse
import boto3 
import ruamel.yaml

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

with open("config.yaml", "r") as file:
    config = yaml.load(file)


AWS_REGION = config['aws_region']
LOCAL_INPUT_DATA_PATH = config['local_input_data_path']
S3_BUCKET_NAME = config['input_data_s3_bucket']
S3_PREFIX = config['input_data_s3_prefix']
USE_CASE = config['use_case']

# Create the s3 prefix pattern: s3_prefix/use_case/use_case.jsonl
s3_object_key = f"{S3_PREFIX}/{USE_CASE}/{USE_CASE}.jsonl"

# Upload local file to S3 with the specified key pattern
print(f"Uploading {LOCAL_INPUT_DATA_PATH} to s3://{S3_BUCKET_NAME}/{s3_object_key}")
boto3.client('s3', region_name=AWS_REGION).upload_file(LOCAL_INPUT_DATA_PATH, S3_BUCKET_NAME, s3_object_key)

# Add or update the config parameters
config['s3_jsonl_file'] = s3_object_key
config['uri_for_uploaded_s3_input_data'] = f"s3://{S3_BUCKET_NAME}/{s3_object_key}"

# Write the updated config back to config.yaml
with open("config.yaml", "w") as f:
    yaml.dump(config, f)