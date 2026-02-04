# AWS Service Mocking Guide with Moto

This guide explains how to use moto for mocking AWS services in tests for the automated LLM finetuning pipeline.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Available Fixtures](#available-fixtures)
5. [Usage Examples](#usage-examples)
6. [Best Practices](#best-practices)
7. [Limitations](#limitations)
8. [Troubleshooting](#troubleshooting)

## Overview

**Moto** is a library that mocks AWS services for testing purposes. It allows you to:

- Test AWS integrations without making real API calls
- Avoid AWS costs during testing
- Run tests faster (no network latency)
- Test error scenarios that are hard to reproduce with real AWS
- Run tests in CI/CD without AWS credentials

The pipeline uses moto to mock:
- **SageMaker**: Training jobs, models, and endpoints
- **S3**: Bucket operations and file storage
- **Bedrock Runtime**: Model invocations (limited support)

## Installation

Moto is already included in `requirements.txt`:

```bash
pip install -r requirements.txt
```

The installation includes specific service extras:
```
moto[sagemaker,s3,bedrock]>=4.2.0
```

## Quick Start

### Basic Test with Moto

```python
import boto3
import pytest

def test_s3_operations(mock_s3):
    """Test S3 operations with moto"""
    # Create S3 client - all calls are mocked
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Create bucket
    s3.create_bucket(Bucket='test-bucket')
    
    # Upload file
    s3.put_object(
        Bucket='test-bucket',
        Key='test.txt',
        Body=b'Hello, World!'
    )
    
    # Download and verify
    response = s3.get_object(Bucket='test-bucket', Key='test.txt')
    content = response['Body'].read()
    
    assert content == b'Hello, World!'
```

### Using AWSClientManager with Moto

```python
def test_with_client_manager(aws_client_manager_with_mocks):
    """Test using AWSClientManager with mocked services"""
    manager = aws_client_manager_with_mocks
    
    # Get clients through manager
    s3 = manager.get_s3_client()
    sagemaker = manager.get_sagemaker_client()
    
    # All operations are mocked
    s3.create_bucket(Bucket='test-bucket')
    response = s3.list_buckets()
    
    assert len(response['Buckets']) == 1
```

## Available Fixtures

All fixtures are defined in `tests/conftest.py`.

### Core Fixtures

#### `aws_credentials`
Provides mock AWS credentials for moto.

```python
def test_something(aws_credentials):
    # AWS credentials are set in environment
    # Use boto3 clients normally
    pass
```

#### `mock_sagemaker`
Mocks SageMaker service.

```python
def test_training_job(mock_sagemaker):
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    # Create training jobs, models, endpoints
    pass
```

#### `mock_s3`
Mocks S3 service.

```python
def test_s3_upload(mock_s3):
    s3 = boto3.client('s3', region_name='us-east-1')
    # Create buckets, upload/download files
    pass
```

#### `mock_bedrock`
Mocks Bedrock Runtime service (limited support).

```python
def test_bedrock(mock_bedrock):
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    # Invoke models (may have limitations)
    pass
```

#### `mock_aws_services`
Mocks all AWS services at once.

```python
def test_multiple_services(mock_aws_services):
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    s3 = boto3.client('s3', region_name='us-east-1')
    # Use multiple services together
    pass
```

### Convenience Fixtures

#### `mock_sagemaker_with_role`
Provides mocked SageMaker with a pre-configured IAM role.

```python
def test_training_job(mock_sagemaker_with_role):
    role_arn = mock_sagemaker_with_role
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    
    # Use role_arn in training job creation
    sagemaker.create_training_job(
        TrainingJobName='test-job',
        RoleArn=role_arn,
        # ... other parameters
    )
```

**Returns**: IAM role ARN (string)

#### `mock_s3_with_bucket`
Provides mocked S3 with a pre-created bucket.

```python
def test_upload(mock_s3_with_bucket):
    bucket_name = mock_s3_with_bucket
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Bucket already exists, upload directly
    s3.put_object(Bucket=bucket_name, Key='file.txt', Body=b'data')
```

**Returns**: Bucket name (string): `'test-finetuning-bucket'`

#### `aws_client_manager_with_mocks`
Provides AWSClientManager configured with moto.

```python
def test_component(aws_client_manager_with_mocks):
    manager = aws_client_manager_with_mocks
    
    # Get clients through manager
    sagemaker = manager.get_sagemaker_client()
    s3 = manager.get_s3_client()
    
    # Use invoke_with_retry for automatic retry logic
    result = manager.invoke_with_retry(s3.list_buckets)
```

**Returns**: Configured `AWSClientManager` instance

## Usage Examples

### Example 1: Testing SageMaker Training Job Creation

```python
def test_create_training_job(mock_sagemaker_with_role):
    """Test creating a SageMaker training job"""
    role_arn = mock_sagemaker_with_role
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    
    # Create training job
    job_name = 'test-training-job'
    sagemaker.create_training_job(
        TrainingJobName=job_name,
        RoleArn=role_arn,
        AlgorithmSpecification={
            'TrainingImage': 'my-training-image:latest',
            'TrainingInputMode': 'File'
        },
        InputDataConfig=[{
            'ChannelName': 'training',
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': 's3://my-bucket/training-data',
                    'S3DataDistributionType': 'FullyReplicated'
                }
            }
        }],
        OutputDataConfig={
            'S3OutputPath': 's3://my-bucket/output'
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
    
    # Verify job was created
    response = sagemaker.describe_training_job(TrainingJobName=job_name)
    assert response['TrainingJobName'] == job_name
    assert response['TrainingJobStatus'] in ['InProgress', 'Completed']
```

### Example 2: Testing S3 Training Data Upload

```python
import json

def test_upload_training_data(mock_s3_with_bucket):
    """Test uploading training data to S3"""
    bucket_name = mock_s3_with_bucket
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Create training examples
    examples = [
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
    jsonl_content = '\n'.join(json.dumps(ex) for ex in examples)
    
    # Upload to S3
    key = 'training-data/customer-support.jsonl'
    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=jsonl_content.encode('utf-8')
    )
    
    # Verify upload
    response = s3.get_object(Bucket=bucket_name, Key=key)
    downloaded = response['Body'].read().decode('utf-8')
    
    # Parse and verify
    downloaded_examples = [json.loads(line) for line in downloaded.strip().split('\n')]
    assert len(downloaded_examples) == len(examples)
    assert downloaded_examples[0]['instruction'] == examples[0]['instruction']
```

### Example 3: Testing SageMaker Endpoint Deployment

```python
def test_deploy_endpoint(mock_sagemaker_with_role):
    """Test deploying a model to SageMaker endpoint"""
    role_arn = mock_sagemaker_with_role
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    
    # Create model
    model_name = 'test-model'
    sagemaker.create_model(
        ModelName=model_name,
        PrimaryContainer={
            'Image': 'my-inference-image:latest',
            'ModelDataUrl': 's3://my-bucket/model.tar.gz'
        },
        ExecutionRoleArn=role_arn
    )
    
    # Create endpoint configuration
    config_name = 'test-endpoint-config'
    sagemaker.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[{
            'VariantName': 'AllTraffic',
            'ModelName': model_name,
            'InstanceType': 'ml.m5.xlarge',
            'InitialInstanceCount': 1
        }]
    )
    
    # Create endpoint
    endpoint_name = 'test-endpoint'
    sagemaker.create_endpoint(
        EndpointName=endpoint_name,
        EndpointConfigName=config_name
    )
    
    # Verify endpoint
    response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
    assert response['EndpointName'] == endpoint_name
    assert response['EndpointStatus'] in ['Creating', 'InService']
```

### Example 4: Testing Multi-Service Integration

```python
def test_pipeline_integration(mock_aws_services):
    """Test integration between SageMaker and S3"""
    # Create IAM role
    iam = boto3.client('iam', region_name='us-east-1')
    role_response = iam.create_role(
        RoleName='test-role',
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    role_arn = role_response['Role']['Arn']
    
    # Upload training data to S3
    s3 = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'pipeline-bucket'
    s3.create_bucket(Bucket=bucket_name)
    s3.put_object(
        Bucket=bucket_name,
        Key='training-data/data.jsonl',
        Body=b'{"instruction": "test", "response": "test"}\n'
    )
    
    # Create SageMaker training job using S3 data
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    sagemaker.create_training_job(
        TrainingJobName='integration-job',
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
    
    # Verify both services work together
    job_response = sagemaker.describe_training_job(TrainingJobName='integration-job')
    assert job_response['TrainingJobName'] == 'integration-job'
    
    s3_response = s3.get_object(Bucket=bucket_name, Key='training-data/data.jsonl')
    assert s3_response['Body'].read() == b'{"instruction": "test", "response": "test"}\n'
```

### Example 5: Testing Error Handling

```python
from botocore.exceptions import ClientError

def test_handle_missing_bucket(mock_s3):
    """Test handling of S3 bucket not found errors"""
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Try to access non-existent bucket
    with pytest.raises(ClientError) as exc_info:
        s3.get_object(Bucket='non-existent-bucket', Key='test.txt')
    
    # Verify error code
    error = exc_info.value
    assert error.response['Error']['Code'] == 'NoSuchBucket'

def test_handle_missing_training_job(mock_sagemaker):
    """Test handling of training job not found errors"""
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    
    # Try to describe non-existent job
    with pytest.raises(ClientError):
        sagemaker.describe_training_job(TrainingJobName='non-existent-job')
```

### Example 6: Testing Resource Cleanup

```python
def test_cleanup_endpoints(mock_sagemaker_with_role):
    """Test cleanup of SageMaker endpoints"""
    role_arn = mock_sagemaker_with_role
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    
    # Create endpoint
    model_name = 'test-model'
    sagemaker.create_model(
        ModelName=model_name,
        PrimaryContainer={
            'Image': 'test-image:latest',
            'ModelDataUrl': 's3://bucket/model.tar.gz'
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
    
    # Cleanup
    sagemaker.delete_endpoint(EndpointName=endpoint_name)
    
    # Verify deletion
    try:
        sagemaker.describe_endpoint(EndpointName=endpoint_name)
        # If it still exists, should be in Deleting status
    except ClientError as e:
        # Endpoint not found is acceptable
        assert e.response['Error']['Code'] in ['ValidationException', 'ResourceNotFound']
```

## Best Practices

### 1. Use Appropriate Fixtures

Choose the right fixture for your test:

- **Single service**: Use `mock_sagemaker`, `mock_s3`, or `mock_bedrock`
- **Multiple services**: Use `mock_aws_services`
- **With AWSClientManager**: Use `aws_client_manager_with_mocks`
- **Need pre-setup**: Use `mock_sagemaker_with_role` or `mock_s3_with_bucket`

### 2. Test Isolation

Each test should be independent:

```python
def test_isolated_operation(mock_s3):
    """Each test gets a fresh mocked environment"""
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # This bucket only exists in this test
    s3.create_bucket(Bucket='test-bucket')
    
    # Other tests won't see this bucket
```

### 3. Realistic Test Data

Use realistic data structures:

```python
def test_with_realistic_data(mock_s3_with_bucket):
    """Use realistic training data format"""
    bucket_name = mock_s3_with_bucket
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Realistic JSONL training data
    training_data = [
        {
            'instruction': 'Respond to customer inquiry',
            'context': 'Customer asks about product availability',
            'response': 'Let me check our inventory for you...'
        }
    ]
    
    jsonl = '\n'.join(json.dumps(ex) for ex in training_data)
    s3.put_object(Bucket=bucket_name, Key='data.jsonl', Body=jsonl.encode())
```

### 4. Test Error Scenarios

Test both success and failure paths:

```python
def test_error_handling(mock_s3):
    """Test error handling with mocked errors"""
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Test missing bucket error
    with pytest.raises(ClientError) as exc_info:
        s3.get_object(Bucket='missing-bucket', Key='file.txt')
    
    assert exc_info.value.response['Error']['Code'] == 'NoSuchBucket'
```

### 5. Use AWSClientManager for Components

When testing components that use AWSClientManager:

```python
def test_component(aws_client_manager_with_mocks):
    """Test component using AWSClientManager"""
    manager = aws_client_manager_with_mocks
    
    # Component uses manager internally
    component = MyComponent(manager)
    result = component.do_something()
    
    assert result is not None
```

### 6. Clean Test Structure

Organize tests clearly:

```python
class TestSageMakerOperations:
    """Group related tests together"""
    
    def test_create_training_job(self, mock_sagemaker_with_role):
        """Test training job creation"""
        pass
    
    def test_list_training_jobs(self, mock_sagemaker_with_role):
        """Test listing training jobs"""
        pass
    
    def test_describe_training_job(self, mock_sagemaker_with_role):
        """Test describing training job"""
        pass
```

## Limitations

### Moto Limitations

1. **Bedrock Support**: Moto's Bedrock support is limited. For complex Bedrock testing, use manual mocks:

```python
def test_bedrock_with_manual_mock():
    """Use manual mock for Bedrock"""
    mock_bedrock = Mock()
    mock_bedrock.invoke_model.return_value = {
        'body': Mock(read=lambda: b'{"response": "test"}')
    }
    
    manager = AWSClientManager(mock_clients={'bedrock-runtime': mock_bedrock})
    # Use manager with mock
```

2. **State Persistence**: Moto state doesn't persist between tests (by design).

3. **Real AWS Behavior**: Moto approximates AWS behavior but may not match exactly in all cases.

4. **Async Operations**: Some async AWS operations (like training job completion) are instant in moto.

### When to Use Real AWS

Consider using real AWS (with `@pytest.mark.aws`) for:

- End-to-end integration tests
- Testing actual model training/inference
- Validating real AWS quotas and limits
- Testing AWS-specific edge cases

## Troubleshooting

### Issue: Import Errors

**Problem**: `ImportError: cannot import name 'mock_aws' from 'moto'`

**Solution**: Ensure moto is installed with service extras:
```bash
pip install 'moto[sagemaker,s3,bedrock]>=4.2.0'
```

### Issue: Credentials Not Found

**Problem**: `NoCredentialsError: Unable to locate credentials`

**Solution**: Use the `aws_credentials` fixture:
```python
def test_something(aws_credentials, mock_s3):
    # Credentials are now set
    pass
```

### Issue: Service Not Mocked

**Problem**: Test makes real AWS API calls

**Solution**: Ensure you're using the correct fixture:
```python
# Wrong - no fixture
def test_s3():
    s3 = boto3.client('s3')  # Makes real calls!

# Correct - with fixture
def test_s3(mock_s3):
    s3 = boto3.client('s3', region_name='us-east-1')  # Mocked
```

### Issue: Moto State Leaking Between Tests

**Problem**: One test affects another

**Solution**: Moto fixtures are function-scoped and should isolate tests automatically. If you see leakage, check for module-level boto3 clients.

### Issue: Bedrock Not Working

**Problem**: Bedrock operations fail with moto

**Solution**: Use manual mocks for Bedrock:
```python
def test_bedrock():
    mock_bedrock = Mock()
    mock_bedrock.invoke_model.return_value = {'body': Mock()}
    
    manager = AWSClientManager(mock_clients={'bedrock-runtime': mock_bedrock})
```

## Running Tests

### Run All Tests with Mocking

```bash
# Run all tests (includes mocked AWS tests)
pytest

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/integration/test_aws_mocking_examples.py

# Run specific test
pytest tests/integration/test_aws_mocking_examples.py::TestS3Mocking::test_create_bucket_and_upload_file
```

### Run Tests with Coverage

```bash
pytest --cov=src --cov-report=html
```

### Skip AWS Integration Tests

```bash
# Skip tests marked with @pytest.mark.aws (real AWS tests)
pytest -m "not aws"
```

## Additional Resources

- [Moto Documentation](https://docs.getmoto.org/)
- [Moto GitHub Repository](https://github.com/getmoto/moto)
- [AWS Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Pytest Fixtures Documentation](https://docs.pytest.org/en/stable/fixture.html)

## Examples in This Repository

See `tests/integration/test_aws_mocking_examples.py` for comprehensive examples of:
- SageMaker training jobs and endpoints
- S3 bucket operations and file uploads
- Multi-service integration tests
- Error handling scenarios
- Resource cleanup testing
- AWSClientManager integration

These examples serve as both documentation and working tests that validate the mocking setup.
