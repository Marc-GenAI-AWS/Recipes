"""List available Bedrock models and inference profiles."""

import boto3
import json

print("Listing available Bedrock models and inference profiles...")
print("=" * 80)

# Create Bedrock client
bedrock = boto3.client('bedrock', region_name='us-east-1')

try:
    # List foundation models
    print("\n1. Foundation Models:")
    print("-" * 80)
    response = bedrock.list_foundation_models()
    
    claude_models = [m for m in response['modelSummaries'] if 'claude' in m['modelId'].lower()]
    
    for model in claude_models:
        print(f"\nModel ID: {model['modelId']}")
        print(f"  Name: {model.get('modelName', 'N/A')}")
        print(f"  Provider: {model.get('providerName', 'N/A')}")
        print(f"  Input Modalities: {model.get('inputModalities', [])}")
        print(f"  Output Modalities: {model.get('outputModalities', [])}")
        if 'inferenceTypesSupported' in model:
            print(f"  Inference Types: {model['inferenceTypesSupported']}")
    
except Exception as e:
    print(f"Error listing foundation models: {e}")

try:
    # List inference profiles
    print("\n\n2. Inference Profiles:")
    print("-" * 80)
    response = bedrock.list_inference_profiles()
    
    for profile in response.get('inferenceProfileSummaries', []):
        print(f"\nProfile ID: {profile['inferenceProfileId']}")
        print(f"  Name: {profile.get('inferenceProfileName', 'N/A')}")
        print(f"  Type: {profile.get('type', 'N/A')}")
        print(f"  Status: {profile.get('status', 'N/A')}")
        if 'models' in profile:
            print(f"  Models: {[m.get('modelId') for m in profile['models']]}")
    
except Exception as e:
    print(f"Error listing inference profiles: {e}")

print("\n" + "=" * 80)
print("Done!")
