"""
Example usage of AWS Client Manager.

This example demonstrates how to use the AWSClientManager to interact with
AWS services (SageMaker, Bedrock, S3) with automatic retry logic and error handling.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.aws_client_manager import AWSClientManager, AWSService
from src.logging_config import configure_logging, LogLevel


def example_basic_usage():
    """Basic usage example with default configuration"""
    print("=== Basic Usage Example ===\n")
    
    # Initialize with default configuration
    manager = AWSClientManager()
    
    # Get clients for different services
    sagemaker = manager.get_sagemaker_client()
    bedrock = manager.get_bedrock_runtime_client()
    s3 = manager.get_s3_client()
    
    print(f"SageMaker client: {sagemaker}")
    print(f"Bedrock Runtime client: {bedrock}")
    print(f"S3 client: {s3}")
    print()


def example_custom_configuration():
    """Example with custom configuration"""
    print("=== Custom Configuration Example ===\n")
    
    # Custom configuration
    config = {
        "region": "us-west-2",
        "retry": {
            "max_attempts": 5,
            "initial_backoff_seconds": 1.0,
            "max_backoff_seconds": 30.0,
        },
        "connect_timeout": 30,
        "read_timeout": 30,
    }
    
    manager = AWSClientManager(config)
    
    print(f"Region: {manager.region}")
    print(f"Max retry attempts: {manager.retry_config.max_attempts}")
    print(f"Initial backoff: {manager.retry_config.initial_backoff_seconds}s")
    print()


def example_with_retry():
    """Example using invoke_with_retry for automatic error handling"""
    print("=== Retry Logic Example ===\n")
    
    # Create manager with mock clients for demonstration
    from unittest.mock import Mock
    
    mock_sagemaker = Mock()
    mock_sagemaker.list_training_jobs.return_value = {
        "TrainingJobSummaries": [
            {"TrainingJobName": "job-1", "TrainingJobStatus": "Completed"},
            {"TrainingJobName": "job-2", "TrainingJobStatus": "InProgress"},
        ]
    }
    
    mock_clients = {"sagemaker": mock_sagemaker}
    manager = AWSClientManager(mock_clients=mock_clients)
    
    # Get client
    sagemaker = manager.get_sagemaker_client()
    
    # Use invoke_with_retry for automatic retry on transient errors
    response = manager.invoke_with_retry(
        sagemaker.list_training_jobs,
        MaxResults=10
    )
    
    print(f"Training jobs: {len(response['TrainingJobSummaries'])}")
    for job in response["TrainingJobSummaries"]:
        print(f"  - {job['TrainingJobName']}: {job['TrainingJobStatus']}")
    print()


def example_credential_validation():
    """Example validating AWS credentials"""
    print("=== Credential Validation Example ===\n")
    
    manager = AWSClientManager()
    
    # Validate credentials (will fail without real AWS credentials)
    is_valid = manager.validate_credentials()
    
    if is_valid:
        print("✓ AWS credentials are valid")
    else:
        print("✗ AWS credentials are invalid or not configured")
    print()


def example_get_client_by_service():
    """Example getting clients by service enum or string"""
    print("=== Get Client by Service Example ===\n")
    
    manager = AWSClientManager()
    
    # Get client by enum
    sagemaker = manager.get_client(AWSService.SAGEMAKER)
    print(f"SageMaker client (by enum): {sagemaker}")
    
    # Get client by string
    bedrock = manager.get_client("bedrock-runtime")
    print(f"Bedrock client (by string): {bedrock}")
    
    # Get client by enum value
    s3 = manager.get_client(AWSService.S3)
    print(f"S3 client (by enum): {s3}")
    print()


def example_mock_clients_for_testing():
    """Example using mock clients for testing"""
    print("=== Mock Clients for Testing Example ===\n")
    
    from unittest.mock import Mock
    
    # Create mock clients
    mock_sagemaker = Mock()
    mock_sagemaker.describe_training_job.return_value = {
        "TrainingJobName": "test-job",
        "TrainingJobStatus": "Completed",
        "TrainingJobArn": "arn:aws:sagemaker:us-east-1:123456789012:training-job/test-job"
    }
    
    mock_bedrock = Mock()
    mock_bedrock.invoke_model.return_value = {
        "body": Mock(read=lambda: b'{"completion": "Hello, world!"}')
    }
    
    mock_s3 = Mock()
    mock_s3.list_buckets.return_value = {
        "Buckets": [
            {"Name": "bucket-1"},
            {"Name": "bucket-2"},
        ]
    }
    
    # Initialize with mock clients
    mock_clients = {
        "sagemaker": mock_sagemaker,
        "bedrock-runtime": mock_bedrock,
        "s3": mock_s3,
    }
    
    manager = AWSClientManager(mock_clients=mock_clients)
    
    # Use mock clients
    sagemaker = manager.get_sagemaker_client()
    job_info = sagemaker.describe_training_job(TrainingJobName="test-job")
    print(f"Training job status: {job_info['TrainingJobStatus']}")
    
    s3 = manager.get_s3_client()
    buckets = s3.list_buckets()
    print(f"S3 buckets: {[b['Name'] for b in buckets['Buckets']]}")
    print()


def example_error_handling():
    """Example demonstrating error handling"""
    print("=== Error Handling Example ===\n")
    
    from unittest.mock import Mock
    from botocore.exceptions import ClientError
    
    # Create mock that raises transient error then succeeds
    mock_sagemaker = Mock()
    mock_sagemaker.describe_training_job.side_effect = [
        ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "DescribeTrainingJob"
        ),
        {"TrainingJobName": "test-job", "TrainingJobStatus": "Completed"}
    ]
    
    mock_clients = {"sagemaker": mock_sagemaker}
    manager = AWSClientManager(mock_clients=mock_clients)
    
    sagemaker = manager.get_sagemaker_client()
    
    # This will retry automatically on throttling error
    try:
        result = manager.invoke_with_retry(
            sagemaker.describe_training_job,
            TrainingJobName="test-job"
        )
        print(f"✓ Successfully retrieved job after retry: {result['TrainingJobStatus']}")
    except Exception as e:
        print(f"✗ Failed after retries: {e}")
    print()


def example_cleanup():
    """Example demonstrating client cleanup"""
    print("=== Client Cleanup Example ===\n")
    
    manager = AWSClientManager()
    
    # Get multiple clients
    manager.get_sagemaker_client()
    manager.get_bedrock_runtime_client()
    manager.get_s3_client()
    
    print(f"Active clients: {len(manager._clients)}")
    
    # Close all clients
    manager.close_all_clients()
    
    print(f"Active clients after cleanup: {len(manager._clients)}")
    print()


def main():
    """Run all examples"""
    # Configure logging
    configure_logging(
        log_dir="logs",
        console_level=LogLevel.INFO,
        enable_file=False  # Disable file logging for examples
    )
    
    print("\n" + "="*60)
    print("AWS Client Manager Examples")
    print("="*60 + "\n")
    
    # Run examples
    example_basic_usage()
    example_custom_configuration()
    example_with_retry()
    example_credential_validation()
    example_get_client_by_service()
    example_mock_clients_for_testing()
    example_error_handling()
    example_cleanup()
    
    print("="*60)
    print("Examples completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
