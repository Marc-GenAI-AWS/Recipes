#!/usr/bin/env python3
"""
Quick test for cross-account SageMaker endpoint access
"""

import boto3
import sagemaker
from sagemaker.predictor import Predictor
from sagemaker.serializers import JSONSerializer
from sagemaker.deserializers import JSONDeserializer

def test_cross_account_endpoint():
    """Test access to the StateStreet endpoint in different account."""
    
    # Target endpoint details
    endpoint_arn = "arn:aws:sagemaker:us-east-1:412677575795:endpoint/StateStreetAWSAILeague2025-team5-0k0t-endpoint"
    endpoint_name = "StateStreetAWSAILeague2025-team5-0k0t-endpoint"
    target_region = "us-east-1"
    
    print("=" * 60)
    print("CROSS-ACCOUNT ENDPOINT ACCESS TEST")
    print("=" * 60)
    print(f"Target endpoint: {endpoint_name}")
    print(f"Target account: 412677575795")
    print(f"Target region: {target_region}")
    print(f"Your current account: <AWS_ACCOUNT_ID>")
    print("-" * 60)
    
    try:
        # Test 1: Check if we can describe the endpoint
        print("\n[TEST 1] Checking endpoint status...")
        sm_client = boto3.client('sagemaker', region_name=target_region)
        
        try:
            response = sm_client.describe_endpoint(EndpointName=endpoint_name)
            print(f"[SUCCESS] Endpoint status: {response['EndpointStatus']}")
            print(f"[INFO] Endpoint config: {response.get('EndpointConfigName', 'N/A')}")
            
            # Test 2: Try to create a predictor and make a request
            print("\n[TEST 2] Testing inference access...")
            
            # Create SageMaker session for the target region
            sagemaker_session = sagemaker.Session(boto_session=boto3.Session(region_name=target_region))
            
            predictor = Predictor(
                endpoint_name=endpoint_name,
                sagemaker_session=sagemaker_session,
                serializer=JSONSerializer(),
                deserializer=JSONDeserializer()
            )
            
            # Simple test payload
            test_payload = {
                "inputs": "What is artificial intelligence?",
                "parameters": {
                    "max_new_tokens": 100,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }
            
            print("[INFO] Sending test request...")
            response = predictor.predict(test_payload)
            print(f"[SUCCESS] Got response: {str(response)[:200]}...")
            
            return True
            
        except Exception as e:
            error_str = str(e)
            print(f"[ERROR] {error_str}")
            
            # Analyze the error to provide guidance
            if "AccessDenied" in error_str or "UnauthorizedOperation" in error_str:
                print("\n[DIAGNOSIS] ACCESS DENIED")
                print("You need cross-account permissions. The endpoint owner must:")
                print("1. Create a resource-based policy allowing your account access")
                print("2. Or provide you with a role to assume in their account")
                
            elif "ValidationException" in error_str and "does not exist" in error_str:
                print("\n[DIAGNOSIS] ENDPOINT NOT FOUND")
                print("The endpoint may not exist or may be in a different region/account")
                
            elif "CredentialsNotFound" in error_str:
                print("\n[DIAGNOSIS] CREDENTIALS ISSUE")
                print("AWS credentials not configured properly")
                
            else:
                print(f"\n[DIAGNOSIS] UNKNOWN ERROR: {error_str}")
            
            return False
            
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        return False

def check_current_credentials():
    """Check what AWS credentials are currently being used."""
    print("\n[CREDENTIALS CHECK]")
    print("-" * 30)
    
    try:
        # Check current identity
        sts_client = boto3.client('sts')
        identity = sts_client.get_caller_identity()
        
        print(f"Current Account: {identity.get('Account')}")
        print(f"Current User/Role: {identity.get('Arn')}")
        print(f"User ID: {identity.get('UserId')}")
        
        # Check if we can assume roles
        print(f"\nCurrent credentials can access account: {identity.get('Account')}")
        print("To access the StateStreet endpoint in account 412677575795, you need:")
        print("1. Cross-account permissions, OR")
        print("2. Credentials for account 412677575795")
        
    except Exception as e:
        print(f"Could not check credentials: {e}")

if __name__ == "__main__":
    check_current_credentials()
    success = test_cross_account_endpoint()
    
    if not success:
        print("\n" + "=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print("1. Contact the StateStreet endpoint owner to grant access")
        print("2. Ask for either:")
        print("   - Resource-based policy allowing your account")
        print("   - IAM role to assume in their account (412677575795)")
        print("3. Or get AWS credentials for account 412677575795")
