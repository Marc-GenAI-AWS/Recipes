"""
Unit tests for AWS Client Manager.

Tests cover:
- Client initialization and configuration
- Client retrieval for all supported services
- Retry logic with exponential backoff
- Error handling for transient and non-transient errors
- Mock client support for testing
- Credential validation
"""

import time
from unittest.mock import Mock, MagicMock, patch, call
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from src.aws_client_manager import (
    AWSClientManager,
    AWSService,
    RetryConfig,
)


class TestRetryConfig:
    """Tests for RetryConfig class"""
    
    def test_default_initialization(self):
        """Test RetryConfig with default values"""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.initial_backoff_seconds == 2.0
        assert config.max_backoff_seconds == 60.0
        assert config.jitter_factor == 0.1
    
    def test_custom_initialization(self):
        """Test RetryConfig with custom values"""
        config = RetryConfig(
            max_attempts=5,
            initial_backoff_seconds=1.0,
            max_backoff_seconds=30.0,
            jitter_factor=0.2,
        )
        
        assert config.max_attempts == 5
        assert config.initial_backoff_seconds == 1.0
        assert config.max_backoff_seconds == 30.0
        assert config.jitter_factor == 0.2
    
    def test_calculate_backoff_exponential(self):
        """Test exponential backoff calculation"""
        config = RetryConfig(
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0,
            jitter_factor=0.0,  # No jitter for predictable testing
        )
        
        # Attempt 0: 2 * (2^0) = 2
        assert config.calculate_backoff(0) == 2.0
        
        # Attempt 1: 2 * (2^1) = 4
        assert config.calculate_backoff(1) == 4.0
        
        # Attempt 2: 2 * (2^2) = 8
        assert config.calculate_backoff(2) == 8.0
        
        # Attempt 3: 2 * (2^3) = 16
        assert config.calculate_backoff(3) == 16.0
    
    def test_calculate_backoff_max_limit(self):
        """Test backoff respects maximum limit"""
        config = RetryConfig(
            initial_backoff_seconds=2.0,
            max_backoff_seconds=10.0,
            jitter_factor=0.0,
        )
        
        # Attempt 10: 2 * (2^10) = 2048, but capped at 10
        assert config.calculate_backoff(10) == 10.0
    
    def test_calculate_backoff_with_jitter(self):
        """Test backoff includes jitter"""
        config = RetryConfig(
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0,
            jitter_factor=0.1,
        )
        
        # With jitter, backoff should be in range [base, base * 1.1]
        base = 2.0
        backoff = config.calculate_backoff(0)
        
        assert base <= backoff <= base * 1.1


class TestAWSClientManager:
    """Tests for AWSClientManager class"""
    
    def test_initialization_default_config(self):
        """Test initialization with default configuration"""
        manager = AWSClientManager()
        
        assert manager.region == "us-east-1"
        assert manager.retry_config.max_attempts == 3
        assert manager._clients == {}
    
    def test_initialization_custom_config(self):
        """Test initialization with custom configuration"""
        config = {
            "region": "us-west-2",
            "aws_access_key_id": "test_key",
            "aws_secret_access_key": "test_secret",
            "retry": {
                "max_attempts": 5,
                "initial_backoff_seconds": 1.0,
            },
            "connect_timeout": 30,
            "read_timeout": 30,
        }
        
        manager = AWSClientManager(config)
        
        assert manager.region == "us-west-2"
        assert manager.aws_access_key_id == "test_key"
        assert manager.aws_secret_access_key == "test_secret"
        assert manager.retry_config.max_attempts == 5
        assert manager.retry_config.initial_backoff_seconds == 1.0
    
    def test_initialization_with_mock_clients(self):
        """Test initialization with mock clients"""
        mock_sagemaker = Mock()
        mock_clients = {"sagemaker": mock_sagemaker}
        
        manager = AWSClientManager(mock_clients=mock_clients)
        
        assert manager.mock_clients == mock_clients
    
    @patch("src.aws_client_manager.boto3.client")
    def test_create_client_real(self, mock_boto_client):
        """Test creating a real boto3 client"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSClientManager({"region": "us-east-1"})
        client = manager._create_client("sagemaker")
        
        assert client == mock_client
        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args[1]
        assert call_kwargs["service_name"] == "sagemaker"
    
    def test_create_client_mock(self):
        """Test creating a mock client"""
        mock_sagemaker = Mock()
        mock_clients = {"sagemaker": mock_sagemaker}
        
        manager = AWSClientManager(mock_clients=mock_clients)
        client = manager._create_client("sagemaker")
        
        assert client == mock_sagemaker
    
    @patch("src.aws_client_manager.boto3.client")
    def test_get_sagemaker_client(self, mock_boto_client):
        """Test getting SageMaker client"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSClientManager()
        client = manager.get_sagemaker_client()
        
        assert client == mock_client
        assert "sagemaker" in manager._clients
        
        # Second call should return cached client
        client2 = manager.get_sagemaker_client()
        assert client2 == mock_client
        assert mock_boto_client.call_count == 1  # Only called once
    
    @patch("src.aws_client_manager.boto3.client")
    def test_get_sagemaker_runtime_client(self, mock_boto_client):
        """Test getting SageMaker Runtime client"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSClientManager()
        client = manager.get_sagemaker_runtime_client()
        
        assert client == mock_client
        assert "sagemaker-runtime" in manager._clients
    
    @patch("src.aws_client_manager.boto3.client")
    def test_get_bedrock_runtime_client(self, mock_boto_client):
        """Test getting Bedrock Runtime client"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSClientManager()
        client = manager.get_bedrock_runtime_client()
        
        assert client == mock_client
        assert "bedrock-runtime" in manager._clients
    
    @patch("src.aws_client_manager.boto3.client")
    def test_get_s3_client(self, mock_boto_client):
        """Test getting S3 client"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSClientManager()
        client = manager.get_s3_client()
        
        assert client == mock_client
        assert "s3" in manager._clients
    
    def test_is_transient_error_connection_errors(self):
        """Test transient error detection for connection errors"""
        manager = AWSClientManager()
        
        # Connection errors are transient
        assert manager.is_transient_error(EndpointConnectionError(endpoint_url="test"))
    
    def test_is_transient_error_throttling(self):
        """Test transient error detection for throttling errors"""
        manager = AWSClientManager()
        
        # Create throttling error
        error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "test_operation"
        )
        
        assert manager.is_transient_error(error)
    
    def test_is_transient_error_service_unavailable(self):
        """Test transient error detection for service unavailable"""
        manager = AWSClientManager()
        
        error = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
            "test_operation"
        )
        
        assert manager.is_transient_error(error)
    
    def test_is_transient_error_non_transient(self):
        """Test transient error detection for non-transient errors"""
        manager = AWSClientManager()
        
        # Validation error is not transient
        error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid input"}},
            "test_operation"
        )
        
        assert not manager.is_transient_error(error)
    
    def test_is_transient_error_generic_exception(self):
        """Test transient error detection for generic exceptions"""
        manager = AWSClientManager()
        
        # Generic exceptions are not transient
        assert not manager.is_transient_error(ValueError("test"))
        assert not manager.is_transient_error(KeyError("test"))
    
    def test_invoke_with_retry_success_first_attempt(self):
        """Test successful invocation on first attempt"""
        manager = AWSClientManager()
        
        mock_func = Mock(return_value="success")
        result = manager.invoke_with_retry(mock_func, arg1="value1")
        
        assert result == "success"
        assert mock_func.call_count == 1
        mock_func.assert_called_with(arg1="value1")
    
    @patch("src.aws_client_manager.time.sleep")
    def test_invoke_with_retry_success_after_retries(self, mock_sleep):
        """Test successful invocation after transient errors"""
        config = {
            "retry": {
                "max_attempts": 3,
                "initial_backoff_seconds": 1.0,
                "jitter_factor": 0.0,
            }
        }
        manager = AWSClientManager(config)
        
        # Fail twice, then succeed
        mock_func = Mock(
            side_effect=[
                ClientError(
                    {"Error": {"Code": "ThrottlingException", "Message": "Throttled"}},
                    "test_op"
                ),
                ClientError(
                    {"Error": {"Code": "ServiceUnavailable", "Message": "Unavailable"}},
                    "test_op"
                ),
                "success"
            ]
        )
        
        result = manager.invoke_with_retry(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2
        
        # Verify exponential backoff
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == 1.0  # First retry: 1 * (2^0)
        assert sleep_calls[1] == 2.0  # Second retry: 1 * (2^1)
    
    @patch("src.aws_client_manager.time.sleep")
    def test_invoke_with_retry_exhausted(self, mock_sleep):
        """Test retry exhaustion with transient errors"""
        config = {"retry": {"max_attempts": 3}}
        manager = AWSClientManager(config)
        
        # Always fail with transient error
        error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Throttled"}},
            "test_op"
        )
        mock_func = Mock(side_effect=error)
        
        with pytest.raises(ClientError) as exc_info:
            manager.invoke_with_retry(mock_func)
        
        assert exc_info.value == error
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between attempts
    
    def test_invoke_with_retry_non_transient_error(self):
        """Test immediate failure with non-transient error"""
        manager = AWSClientManager()
        
        # Non-transient error should not be retried
        error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid"}},
            "test_op"
        )
        mock_func = Mock(side_effect=error)
        
        with pytest.raises(ClientError) as exc_info:
            manager.invoke_with_retry(mock_func)
        
        assert exc_info.value == error
        assert mock_func.call_count == 1  # No retries
    
    @patch("src.aws_client_manager.boto3.client")
    def test_validate_credentials_success(self, mock_boto_client):
        """Test successful credential validation"""
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test"
        }
        mock_boto_client.return_value = mock_sts
        
        manager = AWSClientManager()
        result = manager.validate_credentials()
        
        assert result is True
        mock_sts.get_caller_identity.assert_called_once()
    
    @patch("src.aws_client_manager.boto3.client")
    def test_validate_credentials_failure(self, mock_boto_client):
        """Test failed credential validation"""
        mock_sts = Mock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid token"}},
            "GetCallerIdentity"
        )
        mock_boto_client.return_value = mock_sts
        
        manager = AWSClientManager()
        result = manager.validate_credentials()
        
        assert result is False
    
    @patch("src.aws_client_manager.boto3.client")
    def test_get_client_by_enum(self, mock_boto_client):
        """Test getting client by AWSService enum"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSClientManager()
        
        # Test all services
        client = manager.get_client(AWSService.SAGEMAKER)
        assert client == mock_client
        
        client = manager.get_client(AWSService.BEDROCK_RUNTIME)
        assert client == mock_client
        
        client = manager.get_client(AWSService.S3)
        assert client == mock_client
    
    @patch("src.aws_client_manager.boto3.client")
    def test_get_client_by_string(self, mock_boto_client):
        """Test getting client by service name string"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSClientManager()
        
        client = manager.get_client("sagemaker")
        assert client == mock_client
        
        client = manager.get_client("bedrock-runtime")
        assert client == mock_client
    
    def test_get_client_unsupported_service(self):
        """Test error handling for unsupported service"""
        manager = AWSClientManager()
        
        with pytest.raises(ValueError) as exc_info:
            manager.get_client("unsupported-service")
        
        assert "Unsupported AWS service" in str(exc_info.value)
    
    @patch("src.aws_client_manager.boto3.client")
    def test_close_all_clients(self, mock_boto_client):
        """Test closing all clients"""
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_boto_client.side_effect = [mock_client1, mock_client2]
        
        manager = AWSClientManager()
        manager.get_sagemaker_client()
        manager.get_s3_client()
        
        assert len(manager._clients) == 2
        
        manager.close_all_clients()
        
        assert len(manager._clients) == 0
        mock_client1.close.assert_called_once()
        mock_client2.close.assert_called_once()
    
    def test_close_all_clients_handles_errors(self):
        """Test closing clients handles errors gracefully"""
        mock_client = Mock()
        mock_client.close.side_effect = Exception("Close failed")
        
        manager = AWSClientManager()
        manager._clients["test"] = mock_client
        
        # Should not raise exception
        manager.close_all_clients()
        
        assert len(manager._clients) == 0


class TestAWSClientManagerIntegration:
    """Integration tests for AWS Client Manager with mock services"""
    
    def test_end_to_end_with_mock_clients(self):
        """Test complete workflow with mock clients"""
        # Create mock clients
        mock_sagemaker = Mock()
        mock_sagemaker.describe_training_job.return_value = {
            "TrainingJobName": "test-job",
            "TrainingJobStatus": "Completed"
        }
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = {
            "body": Mock(read=lambda: b'{"response": "test"}')
        }
        
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [{"Key": "test.txt"}]
        }
        
        mock_clients = {
            "sagemaker": mock_sagemaker,
            "bedrock-runtime": mock_bedrock,
            "s3": mock_s3,
        }
        
        # Initialize manager with mocks
        manager = AWSClientManager(mock_clients=mock_clients)
        
        # Get clients and use them
        sagemaker = manager.get_sagemaker_client()
        result = sagemaker.describe_training_job(TrainingJobName="test-job")
        assert result["TrainingJobStatus"] == "Completed"
        
        bedrock = manager.get_bedrock_runtime_client()
        result = bedrock.invoke_model(modelId="test")
        assert result is not None
        
        s3 = manager.get_s3_client()
        result = s3.list_objects_v2(Bucket="test-bucket")
        assert len(result["Contents"]) == 1
    
    @patch("src.aws_client_manager.time.sleep")
    def test_retry_with_multiple_services(self, mock_sleep):
        """Test retry logic works across different services"""
        # Create mock that fails once then succeeds
        mock_sagemaker = Mock()
        mock_sagemaker.describe_training_job.side_effect = [
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Throttled"}},
                "DescribeTrainingJob"
            ),
            {"TrainingJobName": "test-job", "TrainingJobStatus": "Completed"}
        ]
        
        mock_clients = {"sagemaker": mock_sagemaker}
        manager = AWSClientManager(mock_clients=mock_clients)
        
        sagemaker = manager.get_sagemaker_client()
        
        # Use invoke_with_retry
        result = manager.invoke_with_retry(
            sagemaker.describe_training_job,
            TrainingJobName="test-job"
        )
        
        assert result["TrainingJobStatus"] == "Completed"
        assert mock_sagemaker.describe_training_job.call_count == 2
        assert mock_sleep.call_count == 1


class TestAWSServiceEnum:
    """Tests for AWSService enum"""
    
    def test_enum_values(self):
        """Test enum has correct values"""
        assert AWSService.SAGEMAKER.value == "sagemaker"
        assert AWSService.SAGEMAKER_RUNTIME.value == "sagemaker-runtime"
        assert AWSService.BEDROCK_RUNTIME.value == "bedrock-runtime"
        assert AWSService.S3.value == "s3"
    
    def test_enum_from_string(self):
        """Test creating enum from string"""
        assert AWSService("sagemaker") == AWSService.SAGEMAKER
        assert AWSService("bedrock-runtime") == AWSService.BEDROCK_RUNTIME
    
    def test_enum_invalid_string(self):
        """Test error for invalid enum string"""
        with pytest.raises(ValueError):
            AWSService("invalid-service")
