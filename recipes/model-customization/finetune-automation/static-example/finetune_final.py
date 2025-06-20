# SageMaker Llama 3 Fine-tuning Script (Chat Format - Final Version)
import json
import os
import time

# Import AWS settings from aws_settings.py
from aws_settings import AWS_REGION, S3_BUCKET_NAME, SAGEMAKER_ARN_ROLE, HF_Key

# Prepare the training job configuration
job_name = f"final-care-finetune-chat-{int(time.time())}"
region = AWS_REGION
role = SAGEMAKER_ARN_ROLE

# Model and instance configuration
model_id = "meta-textgeneration-llama-3-2-1b"
instance_type = "ml.g5.12xlarge"

# Data configuration - using existing S3 path with settings from aws_settings.py
data_s3_uri = f"s3://{S3_BUCKET_NAME}/datasets/care_plan_chat_v3/careplan-data-chat.jsonl"

# Hyperparameters optimized for chat fine-tuning
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
    "train_file": "/opt/ml/input/data/training/careplan-data-chat.jsonl",
    "validation_split_ratio": "0.2"
}

# Environment variables
environment = {
    "accept_eula": "true",
    "log_level": "error",
    "hf_token": HF_Key  # Using HF_Key from aws_settings.py
}

# Training input configuration
training_input = {
    "ChannelName": "training",
    "DataSource": {
        "S3DataSource": {
            "S3Uri": data_s3_uri,
            "S3DataType": "S3Prefix",
            "S3DataDistributionType": "FullyReplicated"
        }
    },
    "ContentType": "application/jsonlines",
    "InputMode": "File"
}

# Create complete configuration
config = {
    "JobName": job_name,
    "ModelId": model_id,
    "InstanceType": instance_type,
    "InstanceCount": 1,
    "Region": region,
    "RoleARN": role,
    "Hyperparameters": hyperparameters,
    "Environment": environment,
    "TrainingInput": training_input,
    "MaxRetryAttempts": 2,
    "OutputDataConfig": {
        "S3OutputPath": f"s3://{S3_BUCKET_NAME}/models/{job_name}"
    }
}

# Save the configuration to a JSON file for review
with open("finetune_config.json", "w") as f:
    json.dump(config, f, indent=2)



import boto3
from sagemaker.jumpstart.estimator import JumpStartEstimator
from sagemaker.inputs import TrainingInput
boto3.setup_default_session(region_name=AWS_REGION)
estimator = JumpStartEstimator(
    model_id=model_id,
    instance_type=instance_type,
    instance_count=1,
    hyperparameters=hyperparameters,
    environment=environment,
    role=SAGEMAKER_ARN_ROLE,
    max_retry_attempts=2
)
estimator.fit(
    {"training": TrainingInput(
        data_s3_uri,
        content_type="application/jsonlines",
        s3_data_type="S3Prefix"
    )},
    job_name=job_name
)

print("\nScript completed successfully - configuration saved to finetune_config.json")

import shutil
import os

output_dir = os.environ.get("SM_MODEL_DIR", "./output")
os.makedirs(f"{output_dir}/code", exist_ok=True)
shutil.copy("custom_inference.py", f"{output_dir}/code/custom_inference.py")

#model.tar.gz/
#├── config.json
#├── model.safetensors
#├── tokenizer.json
#├── special_tokens_map.json
#└── code/
#    └── inference.py