#!/usr/bin/env python3
"""
Quick script to check what's actually in the S3 model directory
"""

import boto3

def check_s3_contents():
    """Check what files are actually in the S3 model directory"""
    
    # Your specific S3 path
    bucket = "sagemaker-us-west-2-<AWS_ACCOUNT_ID>"
    base_prefix = "fine-tuning-output/lilly-llama-finetune-20251014-225851/meta-textgeneration-llama-3-2-3b-2025-10-15-05-58-52-443/output"
    
    s3_client = boto3.client('s3', region_name='us-west-2')
    
    print("🔍 Checking S3 contents...")
    print(f"Bucket: {bucket}")
    print(f"Base prefix: {base_prefix}")
    print("=" * 60)
    
    try:
        # List everything under the output directory
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=base_prefix,
            Delimiter='/'
        )
        
        print("📁 Directories:")
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                dir_name = prefix['Prefix'].replace(base_prefix, '').strip('/')
                print(f"  - {dir_name}/")
        
        print("\n📄 Files in base directory:")
        if 'Contents' in response:
            for obj in response['Contents']:
                file_path = obj['Key'].replace(base_prefix, '').strip('/')
                if file_path:  # Don't show empty (directory itself)
                    print(f"  - {file_path} ({obj['Size']} bytes)")
        
        # Now check specifically in the model/ subdirectory
        model_prefix = f"{base_prefix}/model"
        print(f"\n📄 Files in model/ subdirectory:")
        print(f"Checking: {model_prefix}")
        
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=model_prefix,
            MaxKeys=20
        )
        
        if 'Contents' in response:
            for obj in response['Contents']:
                file_path = obj['Key']
                file_size = obj['Size']
                print(f"  - {file_path} ({file_size} bytes)")
        else:
            print("  No files found in model/ subdirectory")
            
        # Check if there are any .bin, .safetensors, or config files anywhere
        print(f"\n🔍 Looking for model files (*.bin, *.safetensors, config.json)...")
        
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=base_prefix,
            MaxKeys=100
        )
        
        model_files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                if any(ext in key.lower() for ext in ['.bin', '.safetensors', 'config.json', '.json']):
                    model_files.append(key)
        
        if model_files:
            print("✅ Found potential model files:")
            for file in model_files:
                print(f"  - {file}")
                
            # Determine the correct directory
            if model_files:
                # Get the directory of the first model file
                first_file = model_files[0]
                model_dir = '/'.join(first_file.split('/')[:-1])
                suggested_uri = f"s3://{bucket}/{model_dir}/"
                print(f"\n💡 Suggested model URI: {suggested_uri}")
        else:
            print("❌ No model files found!")
            
    except Exception as e:
        print(f"❌ Error checking S3: {e}")

if __name__ == "__main__":
    check_s3_contents()
