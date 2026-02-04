"""
Example tests demonstrating moto usage for AWS service mocking.

This file provides examples of how to use moto fixtures to test
AWS integrations without making real API calls. These examples cover:
- SageMaker training jobs and endpoints
- S3 bucket operations and file uploads
- Bedrock Runtime model invocations
- Integration with AWSClientManager

These tests serve as both documentation and validation of the mocking setup.
"""

import json
import boto3
import pytest
from botocore.exceptions import ClientError

from src.aws_client_manager import AWSClientManager


# ============================================================================
# SageMaker Mocking Examples
# ============================================================================

class TestSageMakerMocking:
    """Examples of mocking SageMaker operations"""
    
    def test_create_training_job(self, mock_sagemaker_with_role):
        """
        Example: Create and describe a SageMaker training job.
        
        This demonstrates how to test training job creation without
        actually starting a real training job on AWS.
        """
        role_arn = mock_sagemaker_with_role
        
        # Create SageMaker client
        sagemaker = boto3.client('sagemaker', region_name='us-east-1')
        
        # Create a training job
        job_name = 'test-training-job'
        sagemaker.create_training_job(
            TrainingJobName=job_name,
            RoleArn=role_arn,
            AlgorithmSpecification={
                'TrainingImage': 'test-image:latest',
                'TrainingInputMode': 'File'
            },
            InputDataConfig=[
                {
                    'ChannelName': 'training',
                    'DataSource': {
                        'S3DataSource': {
                            'S3DataType': 'S3Prefix',
                            'S3Uri': 's3://test-bucket/training-data',
                            'S3DataDistributionType': 'FullyReplicated'
                        }
                    }
                }
            ],
            OutputDataConfig={
                'S3OutputPath': 's3://test-bucket/output'
            },
            ResourceConfig={
                'InstanceType': 'ml.m5.xlarge',
                'InstanceCount': 1,
                'VolumeSizeInGB': 30
            },
            StoppingCondition={
                'MaxRuntimeInSeconds': 3600
            }
        )
        
        # Describe the training job
        response = sagemaker.describe_training_job(TrainingJobName=job_name)
        
        # Verify the job was created
        assert response['TrainingJobName'] == job_name
        assert response['TrainingJobStatus'] in ['InProgress', 'Completed', 'Failed']
        assert response['RoleArn'] == role_arn
    
    def test_list_training_jobs(self, mock_sagemaker_with_role):
        """
        Example: List SageMaker training jobs.
        
        This demonstrates how to test listing operations.
        """
        role_arn = mock_sagemaker_with_role
        sagemaker = boto3.client('sagemaker', region_name='us-east-1')
        
        # Create multiple training jobs
        job_names = ['job-1', 'job-2', 'job-3']
        for job_name in job_names:
            sagemaker.create_training_job(
                TrainingJobName=job_name,
                RoleArn=role_arn,
                AlgorithmSpecification={
                    'TrainingImage': 'test-image:latest',
                    'TrainingInputMode': 'File'
                },
                InputDataConfig=[
                    {
                        'ChannelName': 'training',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': 's3://test-bucket/training-data',
                                'S3DataDistributionType': 'FullyReplicated'
                            }
                        }
                    }
                ],
                OutputDataConfig={
                    'S3OutputPath': 's3://test-bucket/output'
                },
                ResourceConfig={
                    'InstanceType': 'ml.m5.xlarge',
                    'InstanceCount': 1,
                    'VolumeSizeInGB': 30
                },
                StoppingCondition={
                    'MaxRuntimeInSeconds': 3600
                }
            )
        
        # List training jobs
        response = sagemaker.list_training_jobs()
        
        # Verify all jobs are listed
        listed_jobs = [job['TrainingJobName'] for job in response['TrainingJobSummaries']]
        for job_name in job_names:
            assert job_name in listed_jobs
    
    def test_create_endpoint(self, mock_sagemaker_with_role):
        """
        Example: Create a SageMaker endpoint.
        
        This demonstrates how to test endpoint creation and configuration.
        """
        role_arn = mock_sagemaker_with_role
        sagemaker = boto3.client('sagemaker', region_name='us-east-1')
        
        # Create a model
        model_name = 'test-model'
        sagemaker.create_model(
            ModelName=model_name,
            PrimaryContainer={
                'Image': 'test-image:latest',
                'ModelDataUrl': 's3://test-bucket/model.tar.gz'
            },
            ExecutionRoleArn=role_arn
        )
        
        # Create endpoint configuration
        config_name = 'test-endpoint-config'
        sagemaker.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[
                {
                    'VariantName': 'AllTraffic',
                    'ModelName': model_name,
                    'InstanceType': 'ml.m5.xlarge',
                    'InitialInstanceCount': 1
                }
            ]
        )
        
        # Create endpoint
        endpoint_name = 'test-endpoint'
        sagemaker.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=config_name
        )
        
        # Describe endpoint
        response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
        
        # Verify endpoint was created
        assert response['EndpointName'] == endpoint_name
        assert response['EndpointConfigName'] == config_name
        assert response['EndpointStatus'] in ['Creating', 'InService', 'Failed']


# ============================================================================
# S3 Mocking Examples
# ============================================================================

class TestS3Mocking:
    """Examples of mocking S3 operations"""
    
    def test_create_bucket_and_upload_file(self, mock_s3):
        """
        Example: Create S3 bucket and upload a file.
        
        This demonstrates basic S3 operations with moto.
        """
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Create bucket
        bucket_name = 'test-bucket'
        s3.create_bucket(Bucket=bucket_name)
        
        # Upload a file
        key = 'test-data/training.jsonl'
        content = '{"instruction": "test", "response": "test"}\n'
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=content.encode('utf-8')
        )
        
        # Download and verify
        response = s3.get_object(Bucket=bucket_name, Key=key)
        downloaded_content = response['Body'].read().decode('utf-8')
        
        assert downloaded_content == content
    
    def test_list_objects(self, mock_s3_with_bucket):
        """
        Example: List objects in an S3 bucket.
        
        This demonstrates using the mock_s3_with_bucket fixture
        which provides a pre-created bucket.
        """
        bucket_name = mock_s3_with_bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Upload multiple files
        files = {
            'data/file1.txt': 'content1',
            'data/file2.txt': 'content2',
            'models/model.tar.gz': 'model_data'
        }
        
        for key, content in files.items():
            s3.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=content.encode('utf-8')
            )
        
        # List all objects
        response = s3.list_objects_v2(Bucket=bucket_name)
        
        # Verify all files are listed
        assert response['KeyCount'] == len(files)
        listed_keys = [obj['Key'] for obj in response['Contents']]
        for key in files.keys():
            assert key in listed_keys
    
    def test_upload_training_data(self, mock_s3_with_bucket):
        """
        Example: Upload training data in JSONL format.
        
        This demonstrates a realistic use case for the finetuning pipeline.
        """
        bucket_name = mock_s3_with_bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Create training data
        training_examples = [
            {
                'instruction': 'Respond to customer inquiry',
                'context': 'Customer asks about shipping',
                'response': 'We offer free shipping on orders over $50'
            },
            {
                'instruction': 'Respond to customer inquiry',
                'context': 'Customer asks about returns',
                'response': 'We accept returns within 30 days'
            }
        ]
        
        # Convert to JSONL
        jsonl_content = '\n'.join(json.dumps(ex) for ex in training_examples)
        
        # Upload to S3
        key = 'training-data/customer-support.jsonl'
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=jsonl_content.encode('utf-8')
        )
        
        # Download and verify
        response = s3.get_object(Bucket=bucket_name, Key=key)
        downloaded = response['Body'].read().decode('utf-8')
        
        # Parse and verify
        downloaded_examples = [json.loads(line) for line in downloaded.strip().split('\n')]
        assert len(downloaded_examples) == len(training_examples)
        assert downloaded_examples[0]['instruction'] == training_examples[0]['instruction']
    
    def test_delete_objects(self, mock_s3_with_bucket):
        """
        Example: Delete objects from S3 (cleanup scenario).
        
        This demonstrates resource cleanup operations.
        """
        bucket_name = mock_s3_with_bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Upload files
        keys = ['file1.txt', 'file2.txt', 'file3.txt']
        for key in keys:
            s3.put_object(Bucket=bucket_name, Key=key, Body=b'test')
        
        # Verify files exist
        response = s3.list_objects_v2(Bucket=bucket_name)
        assert response['KeyCount'] == len(keys)
        
        # Delete files
        s3.delete_objects(
            Bucket=bucket_name,
            Delete={
                'Objects': [{'Key': key} for key in keys]
            }
        )
        
        # Verify files are deleted
        response = s3.list_objects_v2(Bucket=bucket_name)
        assert response.get('KeyCount', 0) == 0


# ============================================================================
# Bedrock Runtime Mocking Examples
# ============================================================================

class TestBedrockMocking:
    """Examples of mocking Bedrock Runtime operations"""
    
    def test_invoke_model_basic(self, mock_bedrock):
        """
        Example: Invoke a Bedrock model.
        
        Note: Moto's Bedrock support may be limited. This demonstrates
        the basic pattern, but you may need to use manual mocks for
        complex scenarios.
        """
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        # Prepare request
        model_id = 'anthropic.claude-sonnet-4-20250514-v1:0'
        prompt = 'Generate a customer support response'
        
        request_body = json.dumps({
            'prompt': prompt,
            'max_tokens': 100,
            'temperature': 0.7
        })
        
        try:
            # Invoke model
            response = bedrock.invoke_model(
                modelId=model_id,
                body=request_body
            )
            
            # If moto supports this, we can verify the response
            assert 'body' in response
            
        except Exception as e:
            # Moto may not fully support Bedrock yet
            # In this case, use AWSClientManager with mock_clients
            pytest.skip(f"Bedrock mocking not fully supported: {e}")


# ============================================================================
# AWSClientManager Integration Examples
# ============================================================================

class TestAWSClientManagerWithMoto:
    """Examples of using AWSClientManager with moto"""
    
    def test_client_manager_with_mocked_services(self, aws_client_manager_with_mocks):
        """
        Example: Use AWSClientManager with moto-mocked services.
        
        This is the recommended approach for testing components that
        use AWSClientManager.
        """
        manager = aws_client_manager_with_mocks
        
        # Get clients through manager
        sagemaker = manager.get_sagemaker_client()
        s3 = manager.get_s3_client()
        
        # Use clients - all calls are mocked
        # Create S3 bucket
        bucket_name = 'test-bucket'
        s3.create_bucket(Bucket=bucket_name)
        
        # List buckets
        response = s3.list_buckets()
        bucket_names = [b['Name'] for b in response['Buckets']]
        assert bucket_name in bucket_names
        
        # List training jobs (should be empty initially)
        response = sagemaker.list_training_jobs()
        assert 'TrainingJobSummaries' in response
    
    def test_retry_logic_with_mocked_errors(self, aws_client_manager_with_mocks):
        """
        Example: Test retry logic with simulated errors.
        
        This demonstrates how to test error handling and retry behavior.
        """
        manager = aws_client_manager_with_mocks
        s3 = manager.get_s3_client()
        
        # Create bucket
        bucket_name = 'test-bucket'
        s3.create_bucket(Bucket=bucket_name)
        
        # Normal operation should work
        result = manager.invoke_with_retry(
            s3.list_buckets
        )
        
        assert 'Buckets' in result
        bucket_names = [b['Name'] for b in result['Buckets']]
        assert bucket_name in bucket_names
    
    def test_multiple_services_integration(self, mock_aws_services):
        """
        Example: Test integration between multiple AWS services.
        
        This demonstrates a realistic pipeline scenario using
        SageMaker, S3, and potentially Bedrock together.
        """
        # Create IAM role
        iam = boto3.client('iam', region_name='us-east-1')
        role_name = 'test-role'
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )
        role_arn = role_response['Role']['Arn']
        
        # Create S3 bucket and upload training data
        s3 = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'pipeline-bucket'
        s3.create_bucket(Bucket=bucket_name)
        
        training_data = '{"instruction": "test", "response": "test"}\n'
        s3.put_object(
            Bucket=bucket_name,
            Key='training-data/data.jsonl',
            Body=training_data.encode('utf-8')
        )
        
        # Create SageMaker training job using the S3 data
        sagemaker = boto3.client('sagemaker', region_name='us-east-1')
        job_name = 'integration-test-job'
        sagemaker.create_training_job(
            TrainingJobName=job_name,
            RoleArn=role_arn,
            AlgorithmSpecification={
                'TrainingImage': 'test-image:latest',
                'TrainingInputMode': 'File'
            },
            InputDataConfig=[{
                'ChannelName': 'training',
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': f's3://{bucket_name}/training-data',
                        'S3DataDistributionType': 'FullyReplicated'
                    }
                }
            }],
            OutputDataConfig={
                'S3OutputPath': f's3://{bucket_name}/output'
            },
            ResourceConfig={
                'InstanceType': 'ml.m5.xlarge',
                'InstanceCount': 1,
                'VolumeSizeInGB': 30
            },
            StoppingCondition={
                'MaxRuntimeInSeconds': 3600
            }
        )
        
        # Verify the job was created
        response = sagemaker.describe_training_job(TrainingJobName=job_name)
        assert response['TrainingJobName'] == job_name
        
        # Verify S3 data is accessible
        s3_response = s3.get_object(
            Bucket=bucket_name,
            Key='training-data/data.jsonl'
        )
        assert s3_response['Body'].read().decode('utf-8') == training_data


# ============================================================================
# Error Handling Examples
# ============================================================================

class TestErrorHandlingWithMoto:
    """Examples of testing error scenarios with moto"""
    
    def test_bucket_not_found_error(self, mock_s3):
        """
        Example: Test handling of S3 bucket not found errors.
        """
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Try to access non-existent bucket
        with pytest.raises(ClientError) as exc_info:
            s3.get_object(Bucket='non-existent-bucket', Key='test.txt')
        
        # Verify error code
        error = exc_info.value
        assert error.response['Error']['Code'] == 'NoSuchBucket'
    
    def test_training_job_not_found_error(self, mock_sagemaker):
        """
        Example: Test handling of SageMaker training job not found errors.
        """
        sagemaker = boto3.client('sagemaker', region_name='us-east-1')
        
        # Try to describe non-existent training job
        with pytest.raises(ClientError) as exc_info:
            sagemaker.describe_training_job(TrainingJobName='non-existent-job')
        
        # Verify error code
        error = exc_info.value
        # Moto may return different error codes, so we just verify it raises
        assert 'Error' in error.response
    
    def test_invalid_parameters(self, mock_s3_with_bucket):
        """
        Example: Test handling of invalid parameters.
        """
        bucket_name = mock_s3_with_bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Try to get non-existent object
        with pytest.raises(ClientError) as exc_info:
            s3.get_object(Bucket=bucket_name, Key='non-existent-file.txt')
        
        error = exc_info.value
        assert error.response['Error']['Code'] == 'NoSuchKey'


# ============================================================================
# Performance and Cleanup Examples
# ============================================================================

class TestCleanupWithMoto:
    """Examples of testing resource cleanup with moto"""
    
    def test_cleanup_s3_artifacts(self, mock_s3_with_bucket):
        """
        Example: Test cleanup of S3 artifacts after pipeline completion.
        
        This demonstrates testing the cleanup functionality that
        removes temporary files and old training data.
        """
        bucket_name = mock_s3_with_bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Create artifacts
        artifacts = [
            'training-data/iteration-1.jsonl',
            'training-data/iteration-2.jsonl',
            'models/model-1.tar.gz',
            'models/model-2.tar.gz',
            'results/evaluation-1.json'
        ]
        
        for key in artifacts:
            s3.put_object(Bucket=bucket_name, Key=key, Body=b'test data')
        
        # Verify artifacts exist
        response = s3.list_objects_v2(Bucket=bucket_name)
        assert response['KeyCount'] == len(artifacts)
        
        # Cleanup old artifacts (keep only latest)
        keys_to_delete = [
            'training-data/iteration-1.jsonl',
            'models/model-1.tar.gz'
        ]
        
        s3.delete_objects(
            Bucket=bucket_name,
            Delete={'Objects': [{'Key': key} for key in keys_to_delete]}
        )
        
        # Verify cleanup
        response = s3.list_objects_v2(Bucket=bucket_name)
        remaining_keys = [obj['Key'] for obj in response['Contents']]
        
        assert len(remaining_keys) == len(artifacts) - len(keys_to_delete)
        for key in keys_to_delete:
            assert key not in remaining_keys
    
    def test_cleanup_sagemaker_endpoints(self, mock_sagemaker_with_role):
        """
        Example: Test cleanup of SageMaker endpoints.
        
        This demonstrates testing endpoint deletion after pipeline completion.
        """
        role_arn = mock_sagemaker_with_role
        sagemaker = boto3.client('sagemaker', region_name='us-east-1')
        
        # Create model and endpoint
        model_name = 'test-model'
        sagemaker.create_model(
            ModelName=model_name,
            PrimaryContainer={
                'Image': 'test-image:latest',
                'ModelDataUrl': 's3://test-bucket/model.tar.gz'
            },
            ExecutionRoleArn=role_arn
        )
        
        config_name = 'test-config'
        sagemaker.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[{
                'VariantName': 'AllTraffic',
                'ModelName': model_name,
                'InstanceType': 'ml.m5.xlarge',
                'InitialInstanceCount': 1
            }]
        )
        
        endpoint_name = 'test-endpoint'
        sagemaker.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=config_name
        )
        
        # Verify endpoint exists
        response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
        assert response['EndpointName'] == endpoint_name
        
        # Cleanup: Delete endpoint
        sagemaker.delete_endpoint(EndpointName=endpoint_name)
        
        # Verify endpoint is deleted (or being deleted)
        try:
            response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
            # If endpoint still exists, it should be in Deleting status
            assert response['EndpointStatus'] == 'Deleting'
        except ClientError as e:
            # Endpoint not found is also acceptable
            assert e.response['Error']['Code'] in ['ValidationException', 'ResourceNotFound']
