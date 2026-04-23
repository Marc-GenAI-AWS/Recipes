# AWS Integration Testing Guide

This guide explains how to configure and run AWS integration tests for the automated LLM finetuning pipeline.

## Overview

The test suite includes two types of AWS tests:

1. **Mocked AWS Tests** (default): Use `moto` to simulate AWS services locally without credentials
2. **AWS Integration Tests** (optional): Test against real AWS services with actual credentials

## Test Markers

### AWS-Related Markers

- `@pytest.mark.aws_mock`: Tests using moto-mocked AWS services (no credentials needed)
- `@pytest.mark.aws_integration`: Tests requiring real AWS credentials and services
- `@pytest.mark.requires_sagemaker`: Tests specifically requiring SageMaker
- `@pytest.mark.requires_bedrock`: Tests specifically requiring Bedrock
- `@pytest.mark.requires_s3`: Tests specifically requiring S3

### Example Usage

```python
import pytest

# Mocked AWS test (runs by default)
@pytest.mark.aws_mock
def test_sagemaker_training_mock(mock_sagemaker):
    # Uses moto - no real AWS calls
    pass

# Real AWS integration test (skipped by default)
@pytest.mark.aws_integration
@pytest.mark.requires_sagemaker
def test_sagemaker_training_real(skip_if_no_aws_credentials):
    # Uses real AWS services
    pass
```

## Running Tests

### Run All Tests (Mocked AWS Only)

By default, only mocked AWS tests run:

```bash
pytest
```

### Run Only Mocked AWS Tests

```bash
pytest -m "aws_mock"
```

### Run AWS Integration Tests

To run tests against real AWS services:

```bash
# Enable AWS integration tests
pytest --run-aws-integration

# Run only AWS integration tests
pytest -m "aws_integration" --run-aws-integration

# Run with specific AWS region
pytest --run-aws-integration --aws-region us-west-2

# Run with specific AWS profile
pytest --run-aws-integration --aws-profile my-profile
```

### Skip AWS Integration Tests

AWS integration tests are skipped by default. To explicitly skip them:

```bash
pytest --skip-aws-integration
```

### Run Specific AWS Service Tests

```bash
# Only SageMaker tests
pytest -m "requires_sagemaker"

# Only Bedrock tests
pytest -m "requires_bedrock"

# Only S3 tests
pytest -m "requires_s3"
```

## AWS Credentials Configuration

### Prerequisites for AWS Integration Tests

1. **AWS Account**: Active AWS account with appropriate permissions
2. **AWS Credentials**: Configured credentials (see below)
3. **IAM Permissions**: Required permissions for services being tested

### Configuring AWS Credentials

#### Option 1: AWS CLI Configuration (Recommended)

```bash
# Configure default credentials
aws configure

# Or configure a specific profile
aws configure --profile my-profile
```

#### Option 2: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

#### Option 3: IAM Role (EC2/ECS/Lambda)

If running on AWS infrastructure, use IAM roles attached to the instance/container.

### Verifying Credentials

```bash
# Check current credentials
aws sts get-caller-identity

# Or use the provided script
python config/aws/scripts/validate_permissions.py
```

## Required IAM Permissions

### For SageMaker Tests

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sagemaker:CreateTrainingJob",
        "sagemaker:DescribeTrainingJob",
        "sagemaker:CreateModel",
        "sagemaker:CreateEndpointConfig",
        "sagemaker:CreateEndpoint",
        "sagemaker:DescribeEndpoint",
        "sagemaker:DeleteEndpoint",
        "sagemaker:DeleteEndpointConfig",
        "sagemaker:DeleteModel"
      ],
      "Resource": "*"
    }
  ]
}
```

### For Bedrock Tests

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

### For S3 Tests

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:DeleteBucket",
        "s3:ListBucket"
      ],
      "Resource": "*"
    }
  ]
}
```

See `config/aws/PERMISSIONS_EXPLAINED.md` for complete permission details.

## Test Fixtures

### Mocked AWS Fixtures

These fixtures use moto and don't require credentials:

- `aws_credentials`: Sets up mock AWS credentials
- `mock_sagemaker`: Mocked SageMaker service
- `mock_s3`: Mocked S3 service
- `mock_bedrock`: Mocked Bedrock service
- `mock_aws_services`: All AWS services mocked
- `mock_sagemaker_with_role`: SageMaker with pre-configured IAM role
- `mock_s3_with_bucket`: S3 with pre-created bucket
- `aws_client_manager_with_mocks`: AWSClientManager with mocked services

### AWS Integration Fixtures

These fixtures work with real AWS services:

- `aws_integration_config`: Configuration for AWS integration tests
- `skip_if_no_aws_credentials`: Automatically skip if credentials unavailable

## Writing AWS Integration Tests

### Template for Mocked AWS Test

```python
import pytest
import boto3

@pytest.mark.aws_mock
@pytest.mark.requires_s3
def test_s3_upload_mock(mock_s3_with_bucket):
    """Test S3 upload with mocked service."""
    bucket_name = mock_s3_with_bucket
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Upload file
    s3.put_object(
        Bucket=bucket_name,
        Key='test.txt',
        Body=b'test content'
    )
    
    # Verify upload
    response = s3.get_object(Bucket=bucket_name, Key='test.txt')
    assert response['Body'].read() == b'test content'
```

### Template for AWS Integration Test

```python
import pytest
import boto3

@pytest.mark.aws_integration
@pytest.mark.requires_s3
@pytest.mark.slow
def test_s3_upload_real(skip_if_no_aws_credentials, aws_integration_config):
    """Test S3 upload with real AWS service."""
    region = aws_integration_config['region']
    s3 = boto3.client('s3', region_name=region)
    
    # Create test bucket
    bucket_name = f"test-bucket-{uuid.uuid4()}"
    s3.create_bucket(Bucket=bucket_name)
    
    try:
        # Upload file
        s3.put_object(
            Bucket=bucket_name,
            Key='test.txt',
            Body=b'test content'
        )
        
        # Verify upload
        response = s3.get_object(Bucket=bucket_name, Key='test.txt')
        assert response['Body'].read() == b'test content'
        
    finally:
        # Cleanup
        s3.delete_object(Bucket=bucket_name, Key='test.txt')
        s3.delete_bucket(Bucket=bucket_name)
```

## Best Practices

### 1. Always Use Mocked Tests First

Write mocked tests before integration tests. Mocked tests are:
- Faster to run
- Don't incur AWS costs
- Don't require credentials
- More reliable (no network issues)

### 2. Clean Up Resources

Always clean up AWS resources in integration tests:

```python
@pytest.mark.aws_integration
def test_something(skip_if_no_aws_credentials):
    # Create resources
    resource = create_aws_resource()
    
    try:
        # Test logic
        pass
    finally:
        # Always cleanup
        delete_aws_resource(resource)
```

### 3. Use Unique Names

Use UUIDs or timestamps for resource names to avoid conflicts:

```python
import uuid

bucket_name = f"test-bucket-{uuid.uuid4()}"
endpoint_name = f"test-endpoint-{int(time.time())}"
```

### 4. Mark Tests Appropriately

Use multiple markers for better test organization:

```python
@pytest.mark.aws_integration
@pytest.mark.requires_sagemaker
@pytest.mark.slow
def test_training_job():
    pass
```

### 5. Handle Rate Limits

AWS services have rate limits. Add delays if needed:

```python
import time

@pytest.mark.aws_integration
def test_multiple_calls():
    for i in range(10):
        make_aws_call()
        time.sleep(0.5)  # Avoid rate limits
```

### 6. Use Minimal Resources

For integration tests, use minimal resources to reduce costs:
- Small instance types
- Small datasets
- Short training times
- Quick inference tests

## Cost Considerations

AWS integration tests incur costs:

- **SageMaker Training**: ~$0.50-$5 per test (depending on instance type and duration)
- **SageMaker Endpoints**: ~$0.10-$1 per hour
- **Bedrock API Calls**: ~$0.01-$0.10 per test
- **S3 Storage**: Minimal (<$0.01 per test)

**Recommendation**: Run integration tests sparingly (e.g., before releases, not on every commit).

## Troubleshooting

### Tests Skip with "No AWS credentials available"

**Solution**: Configure AWS credentials (see "Configuring AWS Credentials" above)

### Tests Fail with "Access Denied"

**Solution**: Verify IAM permissions (see "Required IAM Permissions" above)

### Tests Timeout

**Solution**: 
- Check network connectivity
- Verify AWS service availability
- Increase timeout values in test code

### Moto Tests Fail

**Solution**:
- Ensure moto is installed: `pip install moto[all]`
- Check moto version compatibility
- Review moto documentation for service limitations

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run mocked tests
        run: |
          pytest -m "not aws_integration"
      
      - name: Run AWS integration tests
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: us-east-1
        run: |
          pytest -m "aws_integration" --run-aws-integration
```

## Additional Resources

- [AWS Credentials Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [Moto Documentation](https://docs.getmoto.org/)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Project AWS Setup Guide](../config/aws/README.md)
- [AWS Mocking Guide](./AWS_MOCKING_GUIDE.md)

## Summary

- **Default behavior**: Only mocked AWS tests run (fast, no credentials needed)
- **Integration tests**: Opt-in with `--run-aws-integration` flag
- **Markers**: Use appropriate markers for test organization
- **Cleanup**: Always clean up AWS resources in integration tests
- **Cost**: Be mindful of AWS costs when running integration tests
