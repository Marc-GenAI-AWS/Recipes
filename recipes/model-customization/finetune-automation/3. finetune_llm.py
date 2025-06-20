import os
import shutil
import sys
import time
import ruamel.yaml 
import boto3
from sagemaker.jumpstart.estimator import JumpStartEstimator
from sagemaker.inputs import TrainingInput

# Fix for Unicode encoding errors on Windows console
if sys.platform == 'win32':
    # Force UTF-8 encoding for console output
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')



yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

with open("config.yaml", "r") as file:
    config = yaml.load(file)

AWS_REGION = config['aws_region']
SAGEMAKER_ARN_ROLE = config['sagemaker_role']
HF_Key = config['huggingface_token']
USE_CASE = config['use_case']
input_data_s3_uri = config['uri_for_uploaded_s3_input_data']
output_model_files_s3_bucket = config['output_model_files_s3_bucket']
model_id = config['jumpstart_model_id']
instance_type = config['instance_type']

# Use a timestamp to ensure uniqueness but avoid duplicating it
timestamp = int(time.time())
# Use the shorter timestamp format (4-digit) for the job name
short_timestamp = str(timestamp)[-4:]
job_name = f"{USE_CASE}-finetune-{short_timestamp}"
job_name = job_name.replace("_", "-")
region = AWS_REGION
role = SAGEMAKER_ARN_ROLE


# Hyperparameters optimized for chat fine-tuning
# Create training file name based on use case
train_filename = f"{USE_CASE}-data-chat.jsonl"

hyperparameters = {
    "model_name": model_id,
    "instruction_tuned": "False",
    "chat_dataset": "True",            # Critical flag for chat format
    "use_default_template": "False",   # Not using default template
    "chat_template": "Llama3.1",       # Use Llama 3.1 specific template
    "epoch": "3",
    "enable_fsdp": "False",
    "learning_rate": "1e-5",
    "per_device_train_batch_size": "2",
    "gradient_accumulation_steps": "4",
    "lora_r": "16",
    "lora_alpha": "64",
    "lora_dropout": "0.05",
    "target_modules": "q_proj,k_proj,v_proj,o_proj",
    "preprocessing_num_workers": "4",
    "num_workers_dataloader": "4",
    "max_input_length": "2048",
    # The train_file should reference the relative path that will be accessible in the container
    "train_file": "/opt/ml/input/data/training/patient_care_plan.jsonl",
    "validation_split_ratio": "0.2"
}

# Environment variables
environment = {
    "accept_eula": "true",
    "log_level": "error",
    "hf_token": HF_Key
}

# Training input configuration
training_input = {
    "ChannelName": "training",
    "DataSource": {
        "S3DataSource": {
            "S3Uri": input_data_s3_uri,
            "S3DataType": "S3Prefix",
            "S3DataDistributionType": "FullyReplicated"
        }
    },
    "ContentType": "application/jsonlines",
    "InputMode": "File"
}


boto3.setup_default_session(region_name=AWS_REGION)

# Create a bucket name for output if not provided
# Use the sagemaker bucket for output files regardless of what's in config
# This ensures consistency with the user's requested output path
output_model_files_s3_bucket = "amazon-sagemaker-<AWS_ACCOUNT_ID>-us-west-2-798b8de84f6d"

# Define output path for model artifacts using the requested structure
output_path = f"s3://{output_model_files_s3_bucket}/finetuned-models/{USE_CASE}/{job_name}"

# Create the estimator
estimator = JumpStartEstimator(
    model_id=model_id,
    instance_type=instance_type,
    instance_count=1,
    hyperparameters=hyperparameters,
    environment=environment,
    role=SAGEMAKER_ARN_ROLE,
    max_retry_attempts=2,
    output_path=output_path
)
# Check if the S3 URI is properly formatted
if input_data_s3_uri.startswith('s3:///'):
    # Fix triple slash problem if it exists
    input_data_s3_uri = input_data_s3_uri.replace('s3:///', 's3://')

# Print debugging info
print(f"Training data URI: {input_data_s3_uri}")
print(f"Output path: s3://{output_model_files_s3_bucket}/{job_name}/")

# Simplified input specification to avoid path mapping issues
estimator.fit(
    inputs=input_data_s3_uri,  # Using simplified input specification
    job_name=job_name
)

print("\nScript completed successfully")


output_dir = os.environ.get("SM_MODEL_DIR", "./output")
os.makedirs(f"{output_dir}/code", exist_ok=True)
shutil.copy("inference.py", f"{output_dir}/code/inference.py")

# Use the model name format from job_name but change 'finetune' to 'model'
model_name = job_name.replace("finetune", "model")

# Store paths without s3:// prefix as per memory guidelines
config['model_files_s3_bucket'] = f"{output_model_files_s3_bucket}/finetuned-models/{USE_CASE}"
config['model_name'] = model_name

# Make sure the prefix doesn't include the bucket name
model_s3_path = f"{output_model_files_s3_bucket}/finetuned-models/{USE_CASE}/{job_name}"

# Print details for debugging
print(f"Model output path: s3://{model_s3_path}")
print(f"Model name: {model_name}")

# Write back with field order preserved
with open("config.yaml", "w") as f:
    yaml.dump(config, f)

#model.tar.gz/
#├── config.json
#├── model.safetensors
#├── tokenizer.json
#├── special_tokens_map.json
#└── code/
#    └── inference.py