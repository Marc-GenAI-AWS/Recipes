import sagemaker
from sagemaker.huggingface import HuggingFaceModel
import boto3
from aws_settings import AWS_REGION, SAGEMAKER_ARN_ROLE

# Create a boto3 session with the desired region
boto_session = boto3.Session(region_name=AWS_REGION)

# Create a SageMaker session using the boto3 session
sagemaker_session = sagemaker.Session(boto_session=boto_session)

role = SAGEMAKER_ARN_ROLE

# S3 URI to your model tarball
model_data = "s3://amazon-sagemaker-<AWS_ACCOUNT_ID>-us-west-2-798b8de84f6d/finetuned_models/model-files.tar.gz"

# Create the HuggingFace Model object
huggingface_model = HuggingFaceModel(
    model_data=model_data,
    role=role,
    transformers_version="4.49.0",  # Match your model's config
    pytorch_version="2.6.0",        # Use the PyTorch version your model expects
    py_version="py312",             # Python version
    entry_point="inference.py",     # Should be at the root of your tarball
    sagemaker_session=sagemaker_session,
)

# Deploy the model to a SageMaker endpoint
predictor = huggingface_model.deploy(
    initial_instance_count=1,
    instance_type="ml.g5.2xlarge",
    endpoint_name="manual-care-endpoint-marc-v2"
)

input_dialog = {
    "dialog": [
        {"role": "system", "content": "You are a medical assistant that creates comprehensive care plans for patients. Your responses should be concise, professional, and address all medical conditions and cultural considerations."},
        {"role": "user", "content": "Create comprehensive care plan for 45yo Male patient with: Medical Conditions: Hypertension, Diabetes. Cultural Considerations: None."}
    ]
}
response = predictor.predict(input_dialog)
print(response)
# Optional: Clean up endpoint when done
# predictor.delete_endpoint()
