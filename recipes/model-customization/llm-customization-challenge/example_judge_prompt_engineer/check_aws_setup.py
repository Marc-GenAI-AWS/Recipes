#!/usr/bin/env python3
"""
Check AWS setup for SageMaker fine-tuning
"""

import boto3
import json
from botocore.exceptions import NoCredentialsError, ClientError

def check_aws_credentials():
    """Check if AWS credentials are configured."""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print("✓ AWS Credentials configured")
        print(f"  Account ID: {identity['Account']}")
        print(f"  User ARN: {identity['Arn']}")
        return True
    except NoCredentialsError:
        print("✗ AWS credentials not configured")
        print("  Run: aws configure")
        return False
    except Exception as e:
        print(f"✗ Error checking credentials: {e}")
        return False

def check_sagemaker_permissions():
    """Check SageMaker permissions."""
    try:
        sagemaker = boto3.client('sagemaker', region_name='us-west-2')
        
        # Try to list training jobs (should work with basic SageMaker permissions)
        response = sagemaker.list_training_jobs(MaxResults=1)
        print("✓ SageMaker permissions OK")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            print("✗ Insufficient SageMaker permissions")
            print("  Need SageMakerFullAccess policy")
        else:
            print(f"✗ SageMaker error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error checking SageMaker: {e}")
        return False

def check_s3_permissions():
    """Check S3 permissions."""
    try:
        s3 = boto3.client('s3', region_name='us-west-2')
        
        # Try to list buckets
        response = s3.list_buckets()
        print("✓ S3 permissions OK")
        print(f"  Found {len(response['Buckets'])} buckets")
        return True
    except ClientError as e:
        print(f"✗ S3 error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error checking S3: {e}")
        return False

def check_training_data():
    """Check if training data files exist."""
    import os
    
    files_to_check = [
        "data_gen/gaming_data_gen.jsonl",
        "data_gen/money_data_gen.jsonl"
    ]
    
    print("\nTraining Data Files:")
    for file_path in files_to_check:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  ✓ {file_path} ({size:,} bytes)")
        else:
            print(f"  ✗ {file_path} (missing)")

def main():
    print("=" * 50)
    print("AWS SAGEMAKER SETUP CHECK")
    print("=" * 50)
    
    # Check AWS credentials
    if not check_aws_credentials():
        return
    
    print()
    
    # Check SageMaker permissions
    if not check_sagemaker_permissions():
        return
    
    print()
    
    # Check S3 permissions  
    if not check_s3_permissions():
        return
    
    # Check training data
    check_training_data()
    
    print("\n" + "=" * 50)
    print("SETUP STATUS: Ready for SageMaker fine-tuning!")
    print("=" * 50)
    
    print("\nNext steps:")
    print("1. Run: python sagemaker_finetune_training.py")
    print("2. Monitor training in AWS Console")
    print("3. Deploy the fine-tuned model")

if __name__ == "__main__":
    main()
