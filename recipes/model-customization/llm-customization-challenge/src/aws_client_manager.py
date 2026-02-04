"""
AWS Client Manager for the automated LLM finetuning pipeline.

This module provides centralized management of boto3 clients for AWS services:
- SageMaker: Model training and deployment
- Bedrock Runtime: Claude Sonnet 4 for data generation and judging
- S3: Storage for training data, model artifacts, and results

Features:
- Centralized client initialization and configuration
- Retry logic with exponential backoff
- Support for both real AWS clients and mock clients for testing
- Comprehensive error handling
- Integration with pipeline logging framework
"""

import time
from typing import Any, Dict, Optional, Union
from enum import Enum

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionError as BotoConnectionError,
    EndpointConnectionError,
)

from src.logging_config import get_logger, LogLevel, log_with_context


# Module logger
logger = get_logger("aws_client_manager")


class AWSService(Enum):
    """Enumeration of supported AWS services"""
    SAGEMAKER = "sagemaker"
    SAGEMAKER_RUNTIME = "sagemaker-runtime"
    BEDROCK_RUNTIME = "bedrock-runtime"
    S3 = "s3"


class RetryConfig:
    """Configuration for retry logic with exponential backoff"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 60.0,
        jitter_factor: float = 0.1,
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            initial_backoff_seconds: Initial backoff delay in seconds
            max_backoff_seconds: Maximum backoff delay in seconds
            jitter_factor: Jitter factor for randomization (0.0 to 1.0)
        """
        self.max_attempts = max_attempts
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.jitter_factor = jitter_factor
    
    def calculate_backoff(self, attempt: int) -> float:
        """
        Calculate backoff delay for a given attempt using exponential backoff.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Backoff delay in seconds
        """
        import random
        
        # Exponential backoff: initial * (2 ^ attempt)
        backoff = min(
            self.initial_backoff_seconds * (2 ** attempt),
            self.max_backoff_seconds
        )
        
        # Add jitter to avoid thundering herd
        if self.jitter_factor > 0:
            jitter = backoff * self.jitter_factor * random.random()
            backoff += jitter
        
        return backoff


class AWSClientManager:
    """
    Centralized manager for AWS boto3 clients.
    
    This class handles:
    - Client initialization with proper configuration
    - Retry logic for transient errors
    - Error handling and logging
    - Support for mock clients in testing
    
    Example usage:
        # Initialize with configuration
        config = {
            'region': 'us-east-1',
            'retry': {'max_attempts': 3}
        }
        manager = AWSClientManager(config)
        
        # Get clients
        sagemaker = manager.get_sagemaker_client()
        bedrock = manager.get_bedrock_runtime_client()
        s3 = manager.get_s3_client()
        
        # Use clients with automatic retry
        response = manager.invoke_with_retry(
            sagemaker.describe_training_job,
            TrainingJobName='my-job'
        )
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        mock_clients: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize AWS Client Manager.
        
        Args:
            config: Configuration dictionary with AWS settings:
                - region: AWS region (default: us-east-1)
                - aws_access_key_id: AWS access key (optional, uses default credentials)
                - aws_secret_access_key: AWS secret key (optional)
                - aws_session_token: AWS session token (optional)
                - retry: Retry configuration dict (optional)
                - connect_timeout: Connection timeout in seconds (default: 60)
                - read_timeout: Read timeout in seconds (default: 60)
            mock_clients: Dictionary of mock clients for testing (optional)
                Keys should be AWSService enum values or service names
        """
        self.config = config or {}
        self.mock_clients = mock_clients or {}
        self._clients: Dict[str, Any] = {}
        
        # Extract configuration
        self.region = self.config.get("region", "us-east-1")
        self.aws_access_key_id = self.config.get("aws_access_key_id")
        self.aws_secret_access_key = self.config.get("aws_secret_access_key")
        self.aws_session_token = self.config.get("aws_session_token")
        
        # Retry configuration
        retry_config = self.config.get("retry", {})
        self.retry_config = RetryConfig(
            max_attempts=retry_config.get("max_attempts", 3),
            initial_backoff_seconds=retry_config.get("initial_backoff_seconds", 2.0),
            max_backoff_seconds=retry_config.get("max_backoff_seconds", 60.0),
            jitter_factor=retry_config.get("jitter_factor", 0.1),
        )
        
        # Boto3 client configuration
        self.boto_config = Config(
            region_name=self.region,
            retries={"max_attempts": 1},  # We handle retries ourselves
            connect_timeout=self.config.get("connect_timeout", 60),
            read_timeout=self.config.get("read_timeout", 60),
        )
        
        logger.info(
            "AWS Client Manager initialized",
            extra={
                "context": {
                    "region": self.region,
                    "retry_max_attempts": self.retry_config.max_attempts,
                    "mock_mode": bool(self.mock_clients),
                }
            }
        )
    
    def _create_client(self, service_name: str) -> Any:
        """
        Create a boto3 client for the specified service.
        
        Args:
            service_name: Name of the AWS service
            
        Returns:
            Boto3 client instance
        """
        # Check if mock client is provided
        if service_name in self.mock_clients:
            logger.debug(f"Using mock client for {service_name}")
            return self.mock_clients[service_name]
        
        # Build client kwargs
        client_kwargs = {
            "service_name": service_name,
            "config": self.boto_config,
        }
        
        # Add credentials if provided
        if self.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = self.aws_secret_access_key
        if self.aws_session_token:
            client_kwargs["aws_session_token"] = self.aws_session_token
        
        try:
            client = boto3.client(**client_kwargs)
            logger.debug(
                f"Created boto3 client for {service_name}",
                extra={"context": {"service": service_name, "region": self.region}}
            )
            return client
        except Exception as e:
            logger.error(
                f"Failed to create boto3 client for {service_name}",
                extra={
                    "context": {
                        "service": service_name,
                        "region": self.region,
                        "error": str(e),
                    }
                },
                exc_info=True,
            )
            raise
    
    def get_sagemaker_client(self) -> Any:
        """
        Get or create SageMaker client.
        
        Returns:
            Boto3 SageMaker client
        """
        service_name = AWSService.SAGEMAKER.value
        if service_name not in self._clients:
            self._clients[service_name] = self._create_client(service_name)
        return self._clients[service_name]
    
    def get_sagemaker_runtime_client(self) -> Any:
        """
        Get or create SageMaker Runtime client.
        
        Returns:
            Boto3 SageMaker Runtime client
        """
        service_name = AWSService.SAGEMAKER_RUNTIME.value
        if service_name not in self._clients:
            self._clients[service_name] = self._create_client(service_name)
        return self._clients[service_name]
    
    def get_bedrock_runtime_client(self) -> Any:
        """
        Get or create Bedrock Runtime client.
        
        Returns:
            Boto3 Bedrock Runtime client
        """
        service_name = AWSService.BEDROCK_RUNTIME.value
        if service_name not in self._clients:
            self._clients[service_name] = self._create_client(service_name)
        return self._clients[service_name]
    
    def get_s3_client(self) -> Any:
        """
        Get or create S3 client.
        
        Returns:
            Boto3 S3 client
        """
        service_name = AWSService.S3.value
        if service_name not in self._clients:
            self._clients[service_name] = self._create_client(service_name)
        return self._clients[service_name]
    
    def is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and should be retried.
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is transient, False otherwise
        """
        # Connection errors are always transient
        if isinstance(error, (BotoConnectionError, EndpointConnectionError)):
            return True
        
        # Check for specific ClientError codes
        if isinstance(error, ClientError):
            error_code = error.response.get("Error", {}).get("Code", "")
            
            # Transient error codes
            transient_codes = {
                "RequestTimeout",
                "RequestTimeoutException",
                "PriorRequestNotComplete",
                "ConnectionError",
                "HTTPClientError",
                "Throttling",
                "ThrottlingException",
                "ThrottledException",
                "RequestThrottledException",
                "TooManyRequestsException",
                "ProvisionedThroughputExceededException",
                "LimitExceededException",
                "RequestLimitExceeded",
                "ServiceUnavailable",
                "ServiceUnavailableException",
                "InternalError",
                "InternalServerError",
                "InternalFailure",
            }
            
            return error_code in transient_codes
        
        # BotoCoreError can be transient
        if isinstance(error, BotoCoreError):
            return True
        
        return False
    
    def invoke_with_retry(
        self,
        func: callable,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Invoke a function with retry logic for transient errors.
        
        This method implements exponential backoff with jitter for retrying
        AWS API calls that fail with transient errors.
        
        Args:
            func: Function to invoke (typically a boto3 client method)
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            Exception: If all retry attempts are exhausted or a non-transient error occurs
            
        Example:
            response = manager.invoke_with_retry(
                sagemaker.describe_training_job,
                TrainingJobName='my-job'
            )
        """
        last_error = None
        
        for attempt in range(self.retry_config.max_attempts):
            try:
                result = func(*args, **kwargs)
                
                # Log successful retry if not first attempt
                if attempt > 0:
                    func_name = getattr(func, "__name__", str(func))
                    logger.info(
                        f"Successfully invoked {func_name} after {attempt + 1} attempts",
                        extra={
                            "context": {
                                "function": func_name,
                                "attempts": attempt + 1,
                            }
                        }
                    )
                
                return result
                
            except Exception as e:
                last_error = e
                
                # Check if error is transient
                if not self.is_transient_error(e):
                    func_name = getattr(func, "__name__", str(func))
                    logger.error(
                        f"Non-transient error in {func_name}: {str(e)}",
                        extra={
                            "context": {
                                "function": func_name,
                                "error_type": type(e).__name__,
                                "error": str(e),
                            }
                        },
                        exc_info=True,
                    )
                    raise
                
                # Check if we have more attempts
                if attempt < self.retry_config.max_attempts - 1:
                    backoff = self.retry_config.calculate_backoff(attempt)
                    func_name = getattr(func, "__name__", str(func))
                    
                    logger.warning(
                        f"Transient error in {func_name}, retrying in {backoff:.2f}s",
                        extra={
                            "context": {
                                "function": func_name,
                                "attempt": attempt + 1,
                                "max_attempts": self.retry_config.max_attempts,
                                "backoff_seconds": backoff,
                                "error_type": type(e).__name__,
                                "error": str(e),
                            }
                        }
                    )
                    
                    time.sleep(backoff)
                else:
                    func_name = getattr(func, "__name__", str(func))
                    logger.error(
                        f"All retry attempts exhausted for {func_name}",
                        extra={
                            "context": {
                                "function": func_name,
                                "attempts": self.retry_config.max_attempts,
                                "error_type": type(e).__name__,
                                "error": str(e),
                            }
                        },
                        exc_info=True,
                    )
        
        # All retries exhausted
        raise last_error
    
    def validate_credentials(self) -> bool:
        """
        Validate AWS credentials by making a simple API call.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            # Use STS to validate credentials
            sts_client = boto3.client(
                "sts",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_session_token=self.aws_session_token,
                config=self.boto_config,
            )
            
            response = sts_client.get_caller_identity()
            
            logger.info(
                "AWS credentials validated successfully",
                extra={
                    "context": {
                        "account": response.get("Account"),
                        "arn": response.get("Arn"),
                    }
                }
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to validate AWS credentials",
                extra={
                    "context": {
                        "error_type": type(e).__name__,
                        "error": str(e),
                    }
                },
                exc_info=True,
            )
            return False
    
    def get_client(self, service: Union[AWSService, str]) -> Any:
        """
        Get a client for any supported AWS service.
        
        Args:
            service: AWS service (AWSService enum or service name string)
            
        Returns:
            Boto3 client for the service
            
        Raises:
            ValueError: If service is not supported
        """
        # Convert string to enum if needed
        if isinstance(service, str):
            try:
                service = AWSService(service)
            except ValueError:
                raise ValueError(
                    f"Unsupported AWS service: {service}. "
                    f"Supported services: {[s.value for s in AWSService]}"
                )
        
        # Map service to getter method
        service_getters = {
            AWSService.SAGEMAKER: self.get_sagemaker_client,
            AWSService.SAGEMAKER_RUNTIME: self.get_sagemaker_runtime_client,
            AWSService.BEDROCK_RUNTIME: self.get_bedrock_runtime_client,
            AWSService.S3: self.get_s3_client,
        }
        
        getter = service_getters.get(service)
        if not getter:
            raise ValueError(f"No getter method for service: {service}")
        
        return getter()
    
    def close_all_clients(self) -> None:
        """
        Close all active boto3 clients.
        
        This is useful for cleanup, especially in testing.
        """
        for service_name, client in self._clients.items():
            try:
                if hasattr(client, "close"):
                    client.close()
                logger.debug(f"Closed client for {service_name}")
            except Exception as e:
                logger.warning(
                    f"Failed to close client for {service_name}: {str(e)}"
                )
        
        self._clients.clear()
        logger.info("All AWS clients closed")
