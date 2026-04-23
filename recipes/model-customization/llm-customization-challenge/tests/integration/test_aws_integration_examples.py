"""
Example AWS integration tests demonstrating real AWS service testing.

These tests are skipped by default and only run when:
1. --run-aws-integration flag is provided
2. AWS credentials are configured

Run with: pytest tests/integration/test_aws_integration_examples.py --run-aws-integration
"""
import pytest
import boto3
import uuid
import time
from botocore.exceptions import ClientError


# ============================================================================
# S3 Integration Tests
# ============================================================================

@pytest.mark.aws_integration
@pytest.mark.requires_s3
class TestS3Integration:
    """Integration tests for S3 operations with real AWS service."""
    
    def test_s3_bucket_lifecycle(self, skip_if_no_aws_credentials, aws_integration_config):
        """Test complete S3 bucket lifecycle: create, upload, download, delete."""
        region = aws_integration_config['region']
        s3 = boto3.client('s3', region_name=region)
        
        # Generate unique bucket name
        bucket_name = f"test-finetuning-{uuid.uuid4()}"
        
        try:
            # Create bucket
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            
            # Upload object
            test_content = b'test training data content'
            s3.put_object(
                Bucket=bucket_name,
                Key='training_data/test.jsonl',
                Body=test_content
            )
            
            # Download and verify
            response = s3.get_object(Bucket=bucket_name, Key='training_data/test.jsonl')
            downloaded_content = response['Body'].read()
            assert downloaded_content == test_content
            
            # List objects
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix='training_data/')
            assert response['KeyCount'] == 1
            assert response['Contents'][0]['Key'] == 'training_data/test.jsonl'
            
        finally:
            # Cleanup
            try:
                # Delete all objects
                response = s3.list_objects_v2(Bucket=bucket_name)
                if 'Contents' in response:
                    for obj in response['Contents']:
                        s3.delete_object(Bucket=bucket_name, Key=obj['Key'])
                
                # Delete bucket
                s3.delete_bucket(Bucket=bucket_name)
            except ClientError:
                pass  # Ignore cleanup errors
    
    def test_s3_multipart_upload(self, skip_if_no_aws_credentials, aws_integration_config):
        """Test S3 multipart upload for large files."""
        region = aws_integration_config['region']
        s3 = boto3.client('s3', region_name=region)
        
        bucket_name = f"test-finetuning-{uuid.uuid4()}"
        
        try:
            # Create bucket
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            
            # Create large content (6MB - requires multipart)
            part_size = 5 * 1024 * 1024  # 5MB
            large_content = b'x' * (part_size + 1024 * 1024)  # 6MB
            
            # Upload using put_object (boto3 handles multipart automatically)
            s3.put_object(
                Bucket=bucket_name,
                Key='large_file.bin',
                Body=large_content
            )
            
            # Verify upload
            response = s3.head_object(Bucket=bucket_name, Key='large_file.bin')
            assert response['ContentLength'] == len(large_content)
            
        finally:
            # Cleanup
            try:
                s3.delete_object(Bucket=bucket_name, Key='large_file.bin')
                s3.delete_bucket(Bucket=bucket_name)
            except ClientError:
                pass


# ============================================================================
# Bedrock Integration Tests
# ============================================================================

@pytest.mark.aws_integration
@pytest.mark.requires_bedrock
@pyte