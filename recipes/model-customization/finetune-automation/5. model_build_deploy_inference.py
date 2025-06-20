import sagemaker
from sagemaker.huggingface import HuggingFaceModel
import boto3
import ruamel.yaml
import time
import json

print("Loading configuration from config.yaml...")
yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

with open("config.yaml", "r") as file:
    config = yaml.load(file)

AWS_REGION = config['aws_region']
SAGEMAKER_ARN_ROLE = config['sagemaker_role']
raw_model_path = config['model_files_s3_bucket']
use_case = config['use_case']
model_tar_s3_file_path = config['model_tar_s3_file_path']

print(f"Setting up SageMaker session in region: {AWS_REGION}")
boto_session = boto3.Session(region_name=AWS_REGION)
sagemaker_session = sagemaker.Session(boto_session=boto_session)

role = SAGEMAKER_ARN_ROLE

# Use proper S3 path formatting for model data
if model_tar_s3_file_path.startswith('s3://'):
    model_data = model_tar_s3_file_path
else:
    model_data = f"s3://{model_tar_s3_file_path}"
    
# Use shorter 4-digit timestamp format for endpoint and model names
current_time = int(time.time())
short_timestamp = str(current_time)[-4:]
endpoint_name = f"{use_case}-endpoint-{short_timestamp}"
endpoint_name = endpoint_name.replace("_", "-")
model_name = f"{use_case}-model-{short_timestamp}"
model_name = model_name.replace("_", "-")

print(f"Preparing HuggingFaceModel with model_data: {model_data}")
huggingface_model = HuggingFaceModel(
    model_data=model_data,
    role=role,
    transformers_version="4.49.0",  # Adjust to supported version as needed
    pytorch_version="2.6.0",        # Adjust to supported version as needed
    py_version="py312",             # Adjust to supported version as needed
    entry_point="inference.py",
    sagemaker_session=sagemaker_session,
    name=model_name
)

print(f"Deploying model to SageMaker endpoint: {endpoint_name} (this may take several minutes)...")
predictor = huggingface_model.deploy(
    initial_instance_count=1,
    instance_type="ml.g5.2xlarge",
    endpoint_name=endpoint_name,
)
print(f"Deployment complete! Endpoint '{endpoint_name}' is now live.")

# Dynamically load the first dialog from the S3 file
s3_uri = config['uri_for_uploaded_s3_input_data']

def split_s3_path(s3_path):
    # Remove the "s3://" prefix
    path = s3_path.replace("s3://", "", 1)
    # Split at the first slash to separate bucket and key
    bucket, _, key = path.partition("/")
    return bucket, key

# Get bucket and key from the S3 URI
bucket, key = split_s3_path(s3_uri)
print(f"Getting sample dialog from {bucket}/{key}...")

# Fetch the first dialog from the S3 file
s3 = boto3.client("s3", region_name=AWS_REGION)
try:
    response = s3.get_object(Bucket=bucket, Key=key)
    # Read just the first line to get the first sample
    first_line = next(response["Body"].iter_lines())
    sample = json.loads(first_line)
    input_dialog = {"dialog": sample["dialog"]}
    print("Successfully loaded sample dialog:")
    print(json.dumps(input_dialog, indent=2)[:200] + "...")
except Exception as e:
    print(f"Error loading sample dialog: {e}")
    print("Falling back to default dialog...")
    # Fallback to a simple default dialog if there's an error
    input_dialog = {
        "dialog": [
            {"role": "system", "content": "You are an AI assistant. Be helpful and concise."},
            {"role": "user", "content": "Hello, can you help me today?"}
        ]
    }

print("Sending test inference request to the endpoint...")
response = predictor.predict(input_dialog)
print("Inference response:")
print(response)

# Update the fields we need to change
config['endpoint_name'] = endpoint_name
config['model_name'] = model_name

print("Saving endpoint and model names to config.yaml...")
with open("config.yaml", "w") as f:
    yaml.dump(config, f)

print("All steps completed successfully!")
# Optional: Clean up endpoint when done
# print(f"Deleting endpoint {endpoint_name}...")
# predictor.delete_endpoint()
# print("Endpoint deleted.")
