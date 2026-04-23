"""
S3 Upload Script for Synthetic Data Generator Files

This script uploads generated data files to Amazon S3 for use with SageMaker fine-tuning.
"""

import os
import argparse
import boto3
from pathlib import Path

# Import AWS settings from aws_settings.py
from aws_settings import AWS_REGION, S3_BUCKET_NAME

def upload_file_to_s3(local_file_path, s3_key):
    """
    Upload a local file to S3
    
    Args:
        local_file_path: Path to local file
        s3_key: S3 key (path within the bucket)
        
    Returns:
        S3 URI for the uploaded file
    """
    print(f"Uploading {local_file_path} to S3...")
    
    # Initialize S3 client
    s3 = boto3.client('s3', region_name=AWS_REGION)
    
    # Upload file
    s3.upload_file(local_file_path, S3_BUCKET_NAME, s3_key)
    
    # Return S3 URI
    s3_uri = f"s3://{S3_BUCKET_NAME}/{s3_key}"
    print(f"Successfully uploaded to {s3_uri}")
    
    return s3_uri

def main():
    parser = argparse.ArgumentParser(description='Upload generated data to S3 for fine-tuning')
    parser.add_argument('--file', type=str, required=True, 
                        help='Path to JSONL file to upload')
    parser.add_argument('--dataset_name', type=str, required=True, 
                        help='Name for the dataset (used in S3 path)')
    parser.add_argument('--s3_prefix', type=str, default='datasets',
                        help='S3 prefix for storing datasets')
    
    args = parser.parse_args()
    
    # Validate file exists
    if not os.path.exists(args.file):
        print(f"Error: File {args.file} does not exist")
        return
    
    # Create S3 key (path)
    filename = os.path.basename(args.file)
    s3_key = f"{args.s3_prefix}/{args.dataset_name}/{filename}"
    
    # Upload file and get S3 URI
    s3_uri = upload_file_to_s3(args.file, s3_key)
    
    print("=" * 80)
    print(f"Dataset name: {args.dataset_name}")
    print(f"S3 URI for fine-tuning: {s3_uri}")
    print("=" * 80)
    print("Use this S3 URI in your fine-tuning script")
    
    # Write URI to a file for easy access by other scripts
    with open(f"{args.dataset_name}_s3_uri.txt", "w") as f:
        f.write(s3_uri)

if __name__ == "__main__":
    main()
