#!/usr/bin/env python3
"""
SageMaker Model Deployment Script
Deploys fine-tuned Llama models to SageMaker endpoints for inference
"""

import boto3
import sagemaker
from sagemaker.jumpstart.model import JumpStartModel
from sagemaker.predictor import Predictor
from sagemaker.serializers import JSONSerializer
from sagemaker.deserializers import JSONDeserializer
import json
import time
from datetime import datetime
import os

class ModelDeployer:
    def __init__(self, region_name='us-west-2'):
        """Initialize SageMaker session and clients."""
        self.region_name = region_name
        self.sagemaker_session = sagemaker.Session(boto_session=boto3.Session(region_name=region_name))
        self.role = "arn:aws:iam::<AWS_ACCOUNT_ID>:role/service-role/<SAGEMAKER_EXECUTION_ROLE>"
        self.bucket = self.sagemaker_session.default_bucket()
        
        print(f"Region: {self.region_name}")
        print(f"Role: {self.role}")
        print(f"Bucket: {self.bucket}")

    def get_training_job_model_uri(self, training_job_name: str):
        """Get the model artifacts URI from a completed training job."""
        try:
            sm_client = boto3.client('sagemaker', region_name=self.region_name)
            response = sm_client.describe_training_job(TrainingJobName=training_job_name)
            model_artifacts_uri = response['ModelArtifacts']['S3ModelArtifacts']
            
            print(f"Found model artifacts at: {model_artifacts_uri}")
            return model_artifacts_uri
            
        except Exception as e:
            print(f"❌ Failed to get training job details: {e}")
            return None

    def deploy_fine_tuned_model(self, 
                               model_s3_uri: str,
                               endpoint_name: str = None,
                               instance_type: str = "ml.g5.xlarge",
                               initial_instance_count: int = 1):
        """Deploy a fine-tuned model to a SageMaker endpoint."""
        
        if endpoint_name is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            endpoint_name = f"llama-finetuned-{timestamp}"
        
        print(f"Deploying model from: {model_s3_uri}")
        print(f"Endpoint name: {endpoint_name}")
        print(f"Instance type: {instance_type}")
        
        try:
            # Use the working pattern from your old script
            print("Creating JumpStart model with fine-tuned artifacts...")
            
            # Create JumpStart model (this automatically handles the correct inference container)
            model = JumpStartModel(
                model_id="meta-textgeneration-llama-3-2-3b",
                model_version="*",
                role=self.role,
                sagemaker_session=self.sagemaker_session
            )
            
            # For uncompressed files, the model_data should point to the directory with trailing slash
            # This tells SageMaker to load individual files from the directory
            print(f"Setting model data to: {model_s3_uri}")
            model.model_data = model_s3_uri
            
            # Set environment variables including EULA acceptance
            model.env.update({"accept_eula": "true"})
            
            print("Creating model...")
            
            # Deploy to endpoint
            print("Deploying to endpoint... (this may take 10-15 minutes)")
            predictor = model.deploy(
                initial_instance_count=initial_instance_count,
                instance_type=instance_type,
                endpoint_name=endpoint_name,
                serializer=JSONSerializer(),
                deserializer=JSONDeserializer()
            )
            
            print(f"✅ Model deployed successfully!")
            print(f"Endpoint name: {endpoint_name}")
            print(f"Endpoint ARN: arn:aws:sagemaker:{self.region_name}:<AWS_ACCOUNT_ID>:endpoint/{endpoint_name}")
            
            return predictor, endpoint_name
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return None, None

    def test_endpoint(self, predictor, test_prompt: str = None):
        """Test the deployed endpoint with a sample prompt."""
        
        if test_prompt is None:
            test_prompt = "Create a first slide for a retail client seeking to modernize their inventory management system."
        
        print(f"\n🧪 Testing endpoint with prompt: '{test_prompt[:50]}...'")
        
        try:
            # Use the instruction format that matches training data (from working script)
            payload = {
                "inputs": f"### Instruction:\n{test_prompt}\n\n### Response:\n",
                "parameters": {
                    "max_new_tokens": 256,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "do_sample": True,
                    "stop": ["###", "\n\n"]  # Stop tokens to prevent over-generation
                }
            }
            
            print("Sending request to endpoint...")
            response = predictor.predict(payload)
            
            print("\n📝 Model Response:")
            print("=" * 60)
            
            # Handle JumpStart response format (from working script)
            if isinstance(response, dict):
                generated_text = response.get('generated_text', str(response))
            elif isinstance(response, list) and len(response) > 0:
                generated_text = response[0].get('generated_text', str(response[0]))
            else:
                generated_text = str(response)
            
            # Clean up the response - extract just the generated part
            if "### Response:" in generated_text:
                response_text = generated_text.split("### Response:")[-1].strip()
            else:
                response_text = generated_text.replace(payload["inputs"], "").strip()
            
            print(response_text)
            print("=" * 60)
            
            return response
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            print(f"💡 This might be normal - some models need a few minutes to warm up")
            return None

    def list_endpoints(self):
        """List all active SageMaker endpoints."""
        try:
            sm_client = boto3.client('sagemaker', region_name=self.region_name)
            response = sm_client.list_endpoints(StatusEquals='InService')
            
            print("\n📋 Active Endpoints:")
            print("-" * 50)
            for endpoint in response['Endpoints']:
                print(f"Name: {endpoint['EndpointName']}")
                print(f"Status: {endpoint['EndpointStatus']}")
                print(f"Created: {endpoint['CreationTime']}")
                print("-" * 50)
                
            return response['Endpoints']
            
        except Exception as e:
            print(f"❌ Failed to list endpoints: {e}")
            return []

    def delete_endpoint(self, endpoint_name: str):
        """Delete a SageMaker endpoint to save costs."""
        try:
            sm_client = boto3.client('sagemaker', region_name=self.region_name)
            
            print(f"🗑️ Deleting endpoint: {endpoint_name}")
            sm_client.delete_endpoint(EndpointName=endpoint_name)
            
            print(f"✅ Endpoint {endpoint_name} deletion initiated")
            print("Note: It may take a few minutes to fully delete")
            
        except Exception as e:
            print(f"❌ Failed to delete endpoint: {e}")

def main():
    """Main function to deploy and test a fine-tuned model."""
    print("=" * 60)
    print("SAGEMAKER MODEL DEPLOYMENT")
    print("=" * 60)
    
    # Configuration - UPDATE THESE VALUES
    TRAINING_JOB_NAME = "meta-textgeneration-llama-3-2-3b-2025-10-15-05-58-52-443"  # Your successful training job
    USE_CASE = "lilly"  # Change to match your use case
    
    print(f"Training job: {TRAINING_JOB_NAME}")
    print(f"Use case: {USE_CASE}")
    
    try:
        # Initialize deployer
        deployer = ModelDeployer()
        
        # Get the correct model URI from the training job
        print("\n" + "=" * 40)
        print("GETTING MODEL ARTIFACTS URI")
        print("=" * 40)
        model_s3_uri = deployer.get_training_job_model_uri(TRAINING_JOB_NAME)
        
        if not model_s3_uri:
            print("❌ Could not retrieve model artifacts URI. Exiting.")
            return
            
        print(f"Model S3 URI: {model_s3_uri}")
        
        # Check existing endpoints
        print("\n" + "=" * 40)
        print("CHECKING EXISTING ENDPOINTS")
        print("=" * 40)
        existing_endpoints = deployer.list_endpoints()
        
        # Ask user what to do
        print(f"\nFound {len(existing_endpoints)} active endpoints")
        action = input("\nChoose action:\n1. Deploy new endpoint\n2. Test existing endpoint\n3. Delete endpoint\nEnter choice (1-3): ").strip()
        
        if action == "1":
            # Deploy new endpoint
            print("\n" + "=" * 40)
            print("DEPLOYING NEW ENDPOINT")
            print("=" * 40)
            
            endpoint_name = f"{USE_CASE}-finetuned-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            predictor, endpoint_name = deployer.deploy_fine_tuned_model(
                model_s3_uri=model_s3_uri,
                endpoint_name=endpoint_name,
                instance_type="ml.g5.xlarge"  # Adjust if needed
            )
            
            if predictor:
                # Test the endpoint
                print("\n" + "=" * 40)
                print("TESTING ENDPOINT")
                print("=" * 40)
                
                test_prompt = f"Create a first slide for a {USE_CASE} client seeking to modernize their technology infrastructure."
                deployer.test_endpoint(predictor, test_prompt)
                
                print(f"\n🎉 Deployment Complete!")
                print(f"Endpoint: {endpoint_name}")
                print(f"Remember to delete the endpoint when done to avoid charges!")
                
        elif action == "2":
            # Test existing endpoint
            if existing_endpoints:
                print("\nSelect endpoint to test:")
                for i, ep in enumerate(existing_endpoints):
                    print(f"{i+1}. {ep['EndpointName']}")
                
                choice = int(input("Enter number: ")) - 1
                if 0 <= choice < len(existing_endpoints):
                    endpoint_name = existing_endpoints[choice]['EndpointName']
                    
                    # Create predictor for existing endpoint
                    predictor = Predictor(
                        endpoint_name=endpoint_name,
                        sagemaker_session=deployer.sagemaker_session,
                        serializer=JSONSerializer(),
                        deserializer=JSONDeserializer()
                    )
                    
                    test_prompt = input("Enter test prompt (or press Enter for default): ").strip()
                    deployer.test_endpoint(predictor, test_prompt if test_prompt else None)
            else:
                print("No endpoints available to test")
                
        elif action == "3":
            # Delete endpoint
            if existing_endpoints:
                print("\nSelect endpoint to delete:")
                for i, ep in enumerate(existing_endpoints):
                    print(f"{i+1}. {ep['EndpointName']}")
                
                choice = int(input("Enter number: ")) - 1
                if 0 <= choice < len(existing_endpoints):
                    endpoint_name = existing_endpoints[choice]['EndpointName']
                    confirm = input(f"Delete {endpoint_name}? (y/n): ").lower()
                    if confirm == 'y':
                        deployer.delete_endpoint(endpoint_name)
            else:
                print("No endpoints available to delete")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
