#!/usr/bin/env python3
"""
SageMaker JumpStart SDK Fine-tuning Script
Creates and launches fine-tuning jobs for Llama models using the SageMaker Python SDK
"""

import boto3
import sagemaker
from sagemaker.jumpstart.model import JumpStartModel
from sagemaker.jumpstart.estimator import JumpStartEstimator
from sagemaker.inputs import TrainingInput
import json
import time
from datetime import datetime
import os

class SageMakerFineTuner:
    def __init__(self, region_name='us-west-2'):
        """Initialize SageMaker session and clients."""
        self.region_name = region_name
        self.sagemaker_session = sagemaker.Session(boto_session=boto3.Session(region_name=region_name))
        self.role = "arn:aws:iam::<AWS_ACCOUNT_ID>:role/service-role/<SAGEMAKER_EXECUTION_ROLE>"
        self.bucket = self.sagemaker_session.default_bucket()
        
        print(f"Region: {self.region_name}")
        print(f"Role: {self.role}")
        print(f"Bucket: {self.bucket}")

    
    def upload_training_data(self, local_file_path: str, s3_prefix: str = 'training-data') -> str:
        """Upload training data to S3."""
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"Training file not found: {local_file_path}")
        
        # Create S3 path
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        s3_key = f"{s3_prefix}/{timestamp}/{os.path.basename(local_file_path)}"
        s3_uri = f"s3://{self.bucket}/{s3_key}"
        
        print(f"Uploading {local_file_path} to {s3_uri}")
        
        # Upload file
        s3_client = boto3.client('s3', region_name=self.region_name)
        s3_client.upload_file(local_file_path, self.bucket, s3_key)
        
        print(f"Upload complete: {s3_uri}")
        return s3_uri
    
    def create_fine_tuning_job(self, 
                              training_data_s3_uri: str,
                              job_name: str = None,
                              model_id: str = "meta-textgeneration-llama-3-2-3b-instruct",
                              instance_type: str = "ml.g5.12xlarge",
                              max_steps: int = 100,
                              learning_rate: float = 1e-4,
                              batch_size: int = 1,
                              validation_split: float = 0.05):
        """Create and start a fine-tuning job."""
        
        if job_name is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            job_name = f"llama-finetune-{timestamp}"
        
        print(f"Creating fine-tuning job: {job_name}")
        print(f"Model ID: {model_id}")
        print(f"Instance type: {instance_type}")
        print(f"Training data: {training_data_s3_uri}")
        
        # Create the estimator
        estimator = JumpStartEstimator(
            model_id=model_id,
            role=self.role,
            instance_count=1,
            instance_type=instance_type,
            sagemaker_session=self.sagemaker_session,
            environment={
                "accept_eula": "true"  # Required: Accept Meta Llama EULA in Environment
            },
            hyperparameters={
                "chat_dataset": "False",
                "instruction_tuned": "True", 
                "use_default_template": "True",
                "disable_output_compression": "False",
                "epoch": "1",
                "max_steps": str(max_steps),
                "learning_rate": str(learning_rate),
                "per_device_train_batch_size": str(batch_size),
                "per_device_eval_batch_size": str(batch_size),
                "validation_split_ratio": str(validation_split),
                "preprocessing_num_workers": "0",
                "num_workers_dataloader": "0",
                "max_input_length": "2048",
                "gradient_accumulation_steps": "4",
                "lora_r": "16",
                "lora_alpha": "64",
                "lora_dropout": "0.05",
                "target_modules": "q_proj,k_proj,v_proj,o_proj"
            },
            output_path=f"s3://{self.bucket}/fine-tuning-output/{job_name}",
            base_job_name=job_name
        )
        
        # Prepare training input
        training_input = TrainingInput(
            s3_data=training_data_s3_uri,
            content_type="application/jsonlines"
        )
        
        # Start training
        print("Starting training job...")
        estimator.fit({"training": training_input}, wait=False)
        
        return estimator, job_name
    
    def monitor_training_job(self, estimator, job_name: str):
        """Monitor the training job progress."""
        print(f"Monitoring training job: {job_name}")
        print("You can also monitor in the AWS Console:")
        print(f"https://{self.region_name}.console.aws.amazon.com/sagemaker/home?region={self.region_name}#/jobs/{job_name}")
        
        try:
            # Wait for completion
            estimator.fit(wait=True)
            print("Training completed successfully!")
            return True
        except Exception as e:
            print(f"Training failed: {e}")
            return False
    
    def get_dataset_info(self, file_path: str) -> dict:
        """Analyze dataset and return optimal training parameters."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file not found: {file_path}")
        
        # Count lines in the dataset
        with open(file_path, 'r', encoding='utf-8') as f:
            line_count = sum(1 for _ in f)
        
        print(f"Dataset analysis: {line_count} samples found")
        
        # Calculate optimal parameters based on dataset size
        if line_count <= 100:
            # Very small dataset
            batch_size = 1
            max_steps = line_count  # 1 epoch
            validation_split = 0.05  # 5%
        elif line_count <= 500:
            # Small dataset
            batch_size = 1
            max_steps = line_count  # 1 epoch
            validation_split = 0.1   # 10%
        elif line_count <= 1000:
            # Medium dataset
            batch_size = 2
            max_steps = line_count // 2  # 1 epoch with batch_size=2
            validation_split = 0.15  # 15%
        else:
            # Large dataset
            batch_size = 4
            max_steps = min(line_count // 4, 1000)  # Cap at 1000 steps
            validation_split = 0.2   # 20%
        
        return {
            'dataset_size': line_count,
            'batch_size': batch_size,
            'max_steps': max_steps,
            'validation_split': validation_split,
            'epochs_equivalent': max_steps / (line_count / batch_size)
        }

    def deploy_model(self, estimator, endpoint_name: str = None, instance_type: str = "ml.g5.12xlarge"):
        """Deploy the fine-tuned model to an endpoint."""
        if endpoint_name is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            endpoint_name = f"llama-finetuned-{timestamp}"
        
        print(f"Deploying model to endpoint: {endpoint_name}")
        print(f"Using instance type: {instance_type}")
        
        try:
            predictor = estimator.deploy(
                initial_instance_count=1,
                instance_type=instance_type,
                endpoint_name=endpoint_name
            )
            
            print(f"Model deployed successfully!")
            print(f"Endpoint name: {endpoint_name}")
            print(f"Endpoint ARN: arn:aws:sagemaker:{self.region_name}:<AWS_ACCOUNT_ID>:endpoint/{endpoint_name}")
            
            return predictor, endpoint_name
            
        except Exception as e:
            print(f"Deployment failed: {e}")
            return None, None

def main():
    """Main function to run the fine-tuning process."""
    print("=" * 60)
    print("SAGEMAKER JUMPSTART FINE-TUNING")
    print("=" * 60)
    
    # Configuration
    USE_CASE = "state"  # Change this to: "lilly", "gaming", "money", or "uhg"
    INSTANCE_TYPE = "ml.g5.2xlarge"  # Instance type for training and deployment
    
    # Training data file mapping
    training_files = {
        "lilly": "data_gen/lilly_data_gen_cleaned.jsonl",
        "gaming": "data_gen/gaming_data_gen_cleaned.jsonl", 
        "money": "data_gen/money_data_gen_cleaned.jsonl",
        "uhg": "data_gen/uhg_data_gen_cleaned2.jsonl",
        "blueprint": "data_gen/blueprint_data_gen_cleaned.jsonl",
        "disney": "data_gen/disney_data_gen_cleaned.jsonl",
        "security": "data_gen/security_data_gen_cleaned.jsonl",
        "state": "data_gen/state_data_gen.jsonl",
        "cheetah": "data_gen/cheetah_data_gen.jsonl"
    }
    
    if USE_CASE not in training_files:
        print(f"Error: Unknown use case '{USE_CASE}'")
        print(f"Available options: {list(training_files.keys())}")
        return
    
    training_file = training_files[USE_CASE]
    
    if not os.path.exists(training_file):
        print(f"Error: Training file not found: {training_file}")
        print("Please generate training data first using 1-generate_data.py")
        return
    
    print(f"Use case: {USE_CASE}")
    print(f"Training file: {training_file}")
    
    try:
        # Initialize fine-tuner
        fine_tuner = SageMakerFineTuner()
        
        # Analyze dataset and get optimal parameters
        print("\n" + "=" * 40)
        print("ANALYZING DATASET")
        print("=" * 40)
        dataset_info = fine_tuner.get_dataset_info(training_file)
        
        print(f"Optimal parameters calculated:")
        print(f"  - Dataset size: {dataset_info['dataset_size']} samples")
        print(f"  - Batch size: {dataset_info['batch_size']}")
        print(f"  - Max steps: {dataset_info['max_steps']}")
        print(f"  - Validation split: {dataset_info['validation_split']:.1%}")
        print(f"  - Training epochs: {dataset_info['epochs_equivalent']:.1f}")
        
        # Upload training data
        print("\n" + "=" * 40)
        print("UPLOADING TRAINING DATA")
        print("=" * 40)
        s3_uri = fine_tuner.upload_training_data(training_file, f"{USE_CASE}-training-data")
        
        # Create training job
        print("\n" + "=" * 40)
        print("CREATING TRAINING JOB")
        print("=" * 40)
        
        # Create job name with format: usecase-finetune-MMDD-SS (last 2 digits of seconds)
        now = datetime.now()
        timestamp = f"{now.strftime('%m%d')}-{now.strftime('%S')}"
        job_name = f"{USE_CASE}-finetune-{timestamp}"
        
        estimator, job_name = fine_tuner.create_fine_tuning_job(
            training_data_s3_uri=s3_uri,
            job_name=job_name,
            model_id="meta-textgeneration-llama-3-2-3b-instruct",
            instance_type=INSTANCE_TYPE,
            max_steps=dataset_info['max_steps'],
            learning_rate=1e-4,
            batch_size=dataset_info['batch_size'],
            validation_split=dataset_info['validation_split']
        )
        
        print(f"\nTraining job '{job_name}' started successfully!")
        print(f"Monitor progress at: https://us-west-2.console.aws.amazon.com/sagemaker/home?region=us-west-2#/jobs/{job_name}")
        
        # Ask user if they want to wait for completion
        wait_for_completion = input("\nWait for training to complete? (y/n): ").lower().strip()
        
        if wait_for_completion == 'y':
            print("\nWaiting for training to complete...")
            success = fine_tuner.monitor_training_job(estimator, job_name)
            
            if success:
                # Ask about deployment
                deploy_now = input("\nDeploy the fine-tuned model to an endpoint? (y/n): ").lower().strip()
                
                if deploy_now == 'y':
                    endpoint_name = f"{USE_CASE}-finetuned-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    predictor, endpoint_name = fine_tuner.deploy_model(estimator, endpoint_name, INSTANCE_TYPE)
                    
                    if predictor:
                        print(f"\n" + "=" * 60)
                        print("DEPLOYMENT COMPLETE")
                        print("=" * 60)
                        print(f"Endpoint: {endpoint_name}")
                        print(f"Update your model_arns.txt file with:")
                        print(f"{USE_CASE} = arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/{endpoint_name}")
        else:
            print(f"\nTraining job started. Check the AWS Console to monitor progress.")
            print(f"Job name: {job_name}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
