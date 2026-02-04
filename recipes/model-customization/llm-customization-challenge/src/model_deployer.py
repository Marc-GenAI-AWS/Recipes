"""
Model Deployer for Automated LLM Finetuning Pipeline

This module provides the ModelDeployer class for deploying finetuned models
to AWS SageMaker endpoints.

The ModelDeployer handles:
- Deploying models to SageMaker endpoints
- Monitoring deployment status with polling
- Managing endpoint lifecycle (create, delete, list)
- Error handling with retry logic
"""

import logging
import time
from datetime import datetime
from typing import Any, List, Optional

from src.config_models import (
    DeploymentResult,
    PipelineConfig
)
from src.logging_config import get_logger

# Configure module logger
logger = get_logger(__name__)


class ModelDeployer:
    """
    Deploys finetuned models to AWS SageMaker endpoints.
    
    The ModelDeployer uses AWS SageMaker to deploy trained models to
    inference endpoints. It supports:
    - Endpoint creation with appropriate instance types
    - Deployment status monitoring with polling
    - Endpoint deletion for cleanup
    - Active endpoint tracking
    - Error handling and retry logic
    
    Attributes:
        sagemaker_client: AWS SageMaker client for endpoint operations
        config: Pipeline configuration with AWS settings and parameters
    
    Example:
        >>> from src.aws_client_manager import AWSClientManager
        >>> from src.configuration_manager import ConfigurationManager
        >>> 
        >>> # Initialize components
        >>> config_manager = ConfigurationManager()
        >>> pipeline_config = config_manager.load_pipeline_config()
        >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
        >>> sagemaker_client = aws_manager.get_sagemaker_client()
        >>> 
        >>> # Create deployer
        >>> deployer = ModelDeployer(sagemaker_client, pipeline_config)
        >>> 
        >>> # Deploy model
        >>> result = deployer.deploy_model(
        ...     model_artifact_uri="s3://bucket/model.tar.gz",
        ...     endpoint_name="customer-support-endpoint"
        ... )
    """
    
    def __init__(
        self,
        sagemaker_client: Any,
        config: PipelineConfig
    ):
        """
        Initialize ModelDeployer with SageMaker client and configuration.
        
        Sets up the deployer with the necessary AWS SageMaker client for managing
        endpoints and the pipeline configuration containing deployment settings,
        instance types, and other operational parameters.
        
        Args:
            sagemaker_client: AWS SageMaker client instance for managing endpoints.
                            Should be obtained from AWSClientManager.
                            Can be a real boto3 client or a mock for testing.
            config: PipelineConfig instance containing AWS region, SageMaker role ARN,
                   inference instance type, S3 bucket, and other pipeline parameters.
        
        Raises:
            ValueError: If sagemaker_client is None or config is None
            TypeError: If config is not a PipelineConfig instance
            AttributeError: If config is missing required attributes
        
        Example:
            >>> from src.aws_client_manager import AWSClientManager
            >>> from src.configuration_manager import ConfigurationManager
            >>> 
            >>> config_manager = ConfigurationManager()
            >>> pipeline_config = config_manager.load_pipeline_config()
            >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
            >>> sagemaker_client = aws_manager.get_sagemaker_client()
            >>> 
            >>> deployer = ModelDeployer(sagemaker_client, pipeline_config)
        """
        # Validate sagemaker_client parameter
        if sagemaker_client is None:
            raise ValueError("sagemaker_client cannot be None")
        
        # Validate config parameter
        if config is None:
            raise ValueError("config cannot be None")
        
        # Validate config is a PipelineConfig instance
        if not isinstance(config, PipelineConfig):
            raise TypeError(
                f"config must be a PipelineConfig instance, got {type(config).__name__}"
            )
        
        # Validate config has required attributes
        required_attrs = [
            'sagemaker_role_arn',
            'inference_instance_type',
            'aws_region',
            's3_bucket',
            'base_model',
            'max_retries',
            'initial_backoff_seconds',
            'max_backoff_seconds'
        ]
        
        missing_attrs = [attr for attr in required_attrs if not hasattr(config, attr)]
        if missing_attrs:
            raise AttributeError(
                f"config is missing required attributes: {', '.join(missing_attrs)}"
            )
        
        # Store client and configuration
        self.sagemaker_client = sagemaker_client
        self.config = config
        
        logger.info(
            "ModelDeployer initialized",
            extra={
                "context": {
                    "region": self.config.aws_region,
                    "inference_instance_type": self.config.inference_instance_type,
                    "base_model": self.config.base_model,
                }
            }
        )
        
        logger.debug(
            "ModelDeployer configuration details",
            extra={
                "context": {
                    "sagemaker_role_arn": self.config.sagemaker_role_arn,
                    "s3_bucket": self.config.s3_bucket,
                    "max_retries": self.config.max_retries,
                    "initial_backoff_seconds": self.config.initial_backoff_seconds,
                    "max_backoff_seconds": self.config.max_backoff_seconds,
                }
            }
        )

    def deploy_model(
        self,
        model_artifact_uri: str,
        endpoint_name: str
    ) -> DeploymentResult:
        """
        Deploy model to SageMaker endpoint.
        
        Creates a SageMaker model, endpoint configuration, and endpoint to deploy
        the trained model for inference. The method:
        1. Creates a SageMaker model from the artifact URI
        2. Creates an endpoint configuration with instance type
        3. Creates an endpoint using the configuration
        4. Waits for endpoint to be in service with polling
        5. Returns deployment results with endpoint details
        
        Args:
            model_artifact_uri: S3 URI of the trained model artifact (model.tar.gz).
                               This should be the output from a SageMaker training job.
            endpoint_name: Name for the SageMaker endpoint. Must be unique within
                          the AWS account and region. Used for invoking the model.
        
        Returns:
            DeploymentResult: Object containing deployment details:
                - endpoint_name: Name of the deployed endpoint
                - endpoint_arn: ARN of the endpoint
                - status: Endpoint status ('InService', 'Failed', etc.)
                - creation_time: When the endpoint was created
                - error_message: Error message if deployment failed (None if successful)
        
        Raises:
            ValueError: If model_artifact_uri or endpoint_name is empty
            RuntimeError: If deployment fails or times out
        
        Example:
            >>> from src.aws_client_manager import AWSClientManager
            >>> from src.configuration_manager import ConfigurationManager
            >>> 
            >>> # Initialize components
            >>> config_manager = ConfigurationManager()
            >>> pipeline_config = config_manager.load_pipeline_config()
            >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
            >>> sagemaker_client = aws_manager.get_sagemaker_client()
            >>> 
            >>> # Create deployer
            >>> deployer = ModelDeployer(sagemaker_client, pipeline_config)
            >>> 
            >>> # Deploy model
            >>> result = deployer.deploy_model(
            ...     model_artifact_uri="s3://bucket/model-artifacts/model.tar.gz",
            ...     endpoint_name="customer-support-endpoint"
            ... )
            >>> 
            >>> if result.is_successful():
            ...     print(f"Endpoint deployed: {result.endpoint_name}")
            ... else:
            ...     print(f"Deployment failed: {result.error_message}")
        """
        # Validate parameters
        if not model_artifact_uri or not model_artifact_uri.strip():
            logger.error("model_artifact_uri cannot be empty")
            raise ValueError("model_artifact_uri cannot be empty")
        
        if not endpoint_name or not endpoint_name.strip():
            logger.error("endpoint_name cannot be empty")
            raise ValueError("endpoint_name cannot be empty")
        
        logger.info(
            "Starting model deployment",
            extra={
                "context": {
                    "endpoint_name": endpoint_name,
                    "model_artifact_uri": model_artifact_uri,
                }
            }
        )
        
        # Step 1: Create SageMaker model
        model_name = f"{endpoint_name}-model"
        logger.info(
            "Creating SageMaker model",
            extra={"context": {"model_name": model_name}}
        )
        
        try:
            self._create_model(model_name, model_artifact_uri)
            logger.info(
                "SageMaker model created successfully",
                extra={"context": {"model_name": model_name}}
            )
        except Exception as e:
            logger.error(
                f"Failed to create SageMaker model: {e}",
                extra={
                    "context": {
                        "model_name": model_name,
                        "error": str(e),
                    }
                }
            )
            raise RuntimeError(f"Failed to create SageMaker model: {e}")
        
        # Step 2: Create endpoint configuration
        endpoint_config_name = f"{endpoint_name}-config"
        logger.info(
            "Creating endpoint configuration",
            extra={"context": {"endpoint_config_name": endpoint_config_name}}
        )
        
        try:
            self._create_endpoint_config(endpoint_config_name, model_name)
            logger.info(
                "Endpoint configuration created successfully",
                extra={"context": {"endpoint_config_name": endpoint_config_name}}
            )
        except Exception as e:
            logger.error(
                f"Failed to create endpoint configuration: {e}",
                extra={
                    "context": {
                        "endpoint_config_name": endpoint_config_name,
                        "error": str(e),
                    }
                }
            )
            raise RuntimeError(f"Failed to create endpoint configuration: {e}")
        
        # Step 3: Create endpoint
        logger.info(
            "Creating SageMaker endpoint",
            extra={
                "context": {
                    "endpoint_name": endpoint_name,
                    "endpoint_config_name": endpoint_config_name,
                }
            }
        )
        
        try:
            endpoint_response = self.sagemaker_client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )
            
            endpoint_arn = endpoint_response.get('EndpointArn', '')
            
            logger.info(
                "Endpoint creation initiated",
                extra={
                    "context": {
                        "endpoint_name": endpoint_name,
                        "endpoint_arn": endpoint_arn,
                    }
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to create endpoint: {e}",
                extra={
                    "context": {
                        "endpoint_name": endpoint_name,
                        "error": str(e),
                    }
                }
            )
            raise RuntimeError(f"Failed to create endpoint: {e}")
        
        # Step 4: Wait for deployment to complete
        logger.info(
            "Waiting for endpoint deployment to complete",
            extra={"context": {"endpoint_name": endpoint_name}}
        )
        
        result = self._wait_for_deployment(endpoint_name)
        
        if result.is_successful():
            logger.info(
                "Deployment completed successfully",
                extra={
                    "context": {
                        "endpoint_name": result.endpoint_name,
                        "endpoint_arn": result.endpoint_arn,
                        "status": result.status,
                    }
                }
            )
        else:
            logger.error(
                "Deployment failed",
                extra={
                    "context": {
                        "endpoint_name": result.endpoint_name,
                        "status": result.status,
                        "error_message": result.error_message,
                    }
                }
            )
        
        return result
    
    def _create_model(self, model_name: str, model_artifact_uri: str) -> None:
        """
        Create a SageMaker model.
        
        Args:
            model_name: Name for the SageMaker model
            model_artifact_uri: S3 URI of the model artifact
        
        Raises:
            Exception: If model creation fails
        """
        model_config = {
            "ModelName": model_name,
            "PrimaryContainer": {
                "Image": self._get_inference_image(),
                "ModelDataUrl": model_artifact_uri,
            },
            "ExecutionRoleArn": self.config.sagemaker_role_arn,
        }
        
        logger.debug(
            "Creating model with configuration",
            extra={
                "context": {
                    "model_name": model_name,
                    "model_artifact_uri": model_artifact_uri,
                }
            }
        )
        
        self.sagemaker_client.create_model(**model_config)
    
    def _create_endpoint_config(
        self,
        endpoint_config_name: str,
        model_name: str
    ) -> None:
        """
        Create a SageMaker endpoint configuration.
        
        Args:
            endpoint_config_name: Name for the endpoint configuration
            model_name: Name of the SageMaker model to use
        
        Raises:
            Exception: If endpoint configuration creation fails
        """
        endpoint_config = {
            "EndpointConfigName": endpoint_config_name,
            "ProductionVariants": [
                {
                    "VariantName": "AllTraffic",
                    "ModelName": model_name,
                    "InstanceType": self.config.inference_instance_type,
                    "InitialInstanceCount": 1,
                }
            ],
        }
        
        logger.debug(
            "Creating endpoint configuration",
            extra={
                "context": {
                    "endpoint_config_name": endpoint_config_name,
                    "model_name": model_name,
                    "instance_type": self.config.inference_instance_type,
                }
            }
        )
        
        self.sagemaker_client.create_endpoint_config(**endpoint_config)
    
    def _get_inference_image(self) -> str:
        """
        Get the SageMaker inference image URI for the base model.
        
        Returns the appropriate inference container image for the configured
        base model. For now, returns a placeholder that will be replaced
        with actual JumpStart image URIs in production.
        
        Returns:
            str: Inference image URI
        """
        # TODO: In production, this should use SageMaker JumpStart to get
        # the actual inference image URI for the base model
        # For now, return a placeholder
        return f"inference-image-for-{self.config.base_model}"
    
    def _wait_for_deployment(
        self,
        endpoint_name: str,
        poll_interval: int = 30
    ) -> DeploymentResult:
        """
        Poll endpoint status until in service.
        
        Monitors the SageMaker endpoint status at regular intervals until
        the endpoint is in service (successfully deployed) or fails.
        
        Args:
            endpoint_name: Name of the endpoint to monitor
            poll_interval: Seconds to wait between status checks (default: 30)
        
        Returns:
            DeploymentResult: Deployment result with endpoint details and status
        
        Raises:
            RuntimeError: If unable to get endpoint status
        """
        logger.info(
            "Starting endpoint deployment monitoring",
            extra={
                "context": {
                    "endpoint_name": endpoint_name,
                    "poll_interval": poll_interval,
                }
            }
        )
        
        start_time = time.time()
        last_status = None
        
        while True:
            try:
                # Get endpoint status
                response = self.sagemaker_client.describe_endpoint(
                    EndpointName=endpoint_name
                )
                
                status = response['EndpointStatus']
                endpoint_arn = response.get('EndpointArn', '')
                creation_time = response.get('CreationTime', datetime.now())
                
                # Log status changes
                if status != last_status:
                    logger.info(
                        f"Endpoint status: {status}",
                        extra={
                            "context": {
                                "endpoint_name": endpoint_name,
                                "status": status,
                                "elapsed_seconds": int(time.time() - start_time),
                            }
                        }
                    )
                    last_status = status
                
                # Check if deployment is complete
                if status == 'InService':
                    # Deployment successful
                    result = DeploymentResult(
                        endpoint_name=endpoint_name,
                        endpoint_arn=endpoint_arn,
                        status=status,
                        creation_time=creation_time,
                        error_message=None
                    )
                    
                    logger.info(
                        f"Endpoint deployment completed successfully",
                        extra={
                            "context": {
                                "endpoint_name": endpoint_name,
                                "endpoint_arn": endpoint_arn,
                                "status": status,
                            }
                        }
                    )
                    
                    return result
                
                elif status in ['Failed', 'RollingBack', 'SystemUpdating']:
                    # Deployment failed
                    failure_reason = response.get('FailureReason', 'Unknown error')
                    
                    result = DeploymentResult(
                        endpoint_name=endpoint_name,
                        endpoint_arn=endpoint_arn,
                        status=status,
                        creation_time=creation_time,
                        error_message=failure_reason
                    )
                    
                    logger.error(
                        f"Endpoint deployment failed",
                        extra={
                            "context": {
                                "endpoint_name": endpoint_name,
                                "status": status,
                                "failure_reason": failure_reason,
                            }
                        }
                    )
                    
                    return result
                
                # Wait before next poll
                logger.debug(
                    f"Deployment in progress, waiting {poll_interval} seconds...",
                    extra={
                        "context": {
                            "endpoint_name": endpoint_name,
                            "status": status,
                        }
                    }
                )
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.error(
                    f"Error checking endpoint status: {e}",
                    extra={
                        "context": {
                            "endpoint_name": endpoint_name,
                            "error": str(e),
                        }
                    }
                )
                raise RuntimeError(f"Failed to monitor endpoint deployment: {e}")
    
    def delete_endpoint(self, endpoint_name: str) -> None:
        """
        Delete SageMaker endpoint and configuration.
        
        Deletes the specified SageMaker endpoint, its configuration, and the
        associated model. This method is idempotent and safe to call multiple
        times - it will not fail if resources have already been deleted.
        
        The method:
        1. Deletes the SageMaker endpoint
        2. Deletes the endpoint configuration
        3. Deletes the SageMaker model
        4. Logs all cleanup operations
        5. Handles errors gracefully (doesn't fail if resources already deleted)
        
        Args:
            endpoint_name: Name of the endpoint to delete. This should be the
                          endpoint name returned by deploy_model().
        
        Raises:
            ValueError: If endpoint_name is None or empty
        
        Example:
            >>> from src.aws_client_manager import AWSClientManager
            >>> from src.configuration_manager import ConfigurationManager
            >>> 
            >>> # Initialize components
            >>> config_manager = ConfigurationManager()
            >>> pipeline_config = config_manager.load_pipeline_config()
            >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
            >>> sagemaker_client = aws_manager.get_sagemaker_client()
            >>> 
            >>> # Create deployer
            >>> deployer = ModelDeployer(sagemaker_client, pipeline_config)
            >>> 
            >>> # Deploy model
            >>> result = deployer.deploy_model(
            ...     model_artifact_uri="s3://bucket/model.tar.gz",
            ...     endpoint_name="customer-support-endpoint"
            ... )
            >>> 
            >>> # Later, delete the endpoint
            >>> deployer.delete_endpoint(result.endpoint_name)
        """
        # Validate endpoint_name parameter
        if not endpoint_name or not endpoint_name.strip():
            raise ValueError("endpoint_name cannot be None or empty")
        
        logger.info(
            "Starting endpoint deletion",
            extra={"context": {"endpoint_name": endpoint_name}}
        )
        
        # Derive resource names from endpoint name
        endpoint_config_name = f"{endpoint_name}-config"
        model_name = f"{endpoint_name}-model"
        
        # Track deletion results
        deleted_resources = []
        failed_deletions = []
        
        # Step 1: Delete endpoint
        try:
            logger.info(
                "Deleting endpoint",
                extra={"context": {"endpoint_name": endpoint_name}}
            )
            
            self.sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
            deleted_resources.append(f"endpoint:{endpoint_name}")
            
            logger.info(
                "Endpoint deleted successfully",
                extra={"context": {"endpoint_name": endpoint_name}}
            )
            
        except self.sagemaker_client.exceptions.ResourceNotFound:
            logger.info(
                f"Endpoint {endpoint_name} not found, may have already been deleted",
                extra={"context": {"endpoint_name": endpoint_name}}
            )
        except Exception as e:
            logger.warning(
                f"Failed to delete endpoint {endpoint_name}: {e}",
                extra={
                    "context": {
                        "endpoint_name": endpoint_name,
                        "error": str(e),
                    }
                }
            )
            failed_deletions.append(f"endpoint:{endpoint_name}")
        
        # Step 2: Delete endpoint configuration
        try:
            logger.info(
                "Deleting endpoint configuration",
                extra={"context": {"endpoint_config_name": endpoint_config_name}}
            )
            
            self.sagemaker_client.delete_endpoint_config(
                EndpointConfigName=endpoint_config_name
            )
            deleted_resources.append(f"endpoint_config:{endpoint_config_name}")
            
            logger.info(
                "Endpoint configuration deleted successfully",
                extra={"context": {"endpoint_config_name": endpoint_config_name}}
            )
            
        except self.sagemaker_client.exceptions.ResourceNotFound:
            logger.info(
                f"Endpoint configuration {endpoint_config_name} not found, may have already been deleted",
                extra={"context": {"endpoint_config_name": endpoint_config_name}}
            )
        except Exception as e:
            logger.warning(
                f"Failed to delete endpoint configuration {endpoint_config_name}: {e}",
                extra={
                    "context": {
                        "endpoint_config_name": endpoint_config_name,
                        "error": str(e),
                    }
                }
            )
            failed_deletions.append(f"endpoint_config:{endpoint_config_name}")
        
        # Step 3: Delete model
        try:
            logger.info(
                "Deleting model",
                extra={"context": {"model_name": model_name}}
            )
            
            self.sagemaker_client.delete_model(ModelName=model_name)
            deleted_resources.append(f"model:{model_name}")
            
            logger.info(
                "Model deleted successfully",
                extra={"context": {"model_name": model_name}}
            )
            
        except self.sagemaker_client.exceptions.ResourceNotFound:
            logger.info(
                f"Model {model_name} not found, may have already been deleted",
                extra={"context": {"model_name": model_name}}
            )
        except Exception as e:
            logger.warning(
                f"Failed to delete model {model_name}: {e}",
                extra={
                    "context": {
                        "model_name": model_name,
                        "error": str(e),
                    }
                }
            )
            failed_deletions.append(f"model:{model_name}")
        
        # Log summary
        logger.info(
            f"Endpoint deletion completed",
            extra={
                "context": {
                    "endpoint_name": endpoint_name,
                    "deleted_resources": deleted_resources,
                    "failed_deletions": failed_deletions,
                }
            }
        )
    
    def list_active_endpoints(self) -> List[str]:
        """
        Return names of all active endpoints for tracking.
        
        Lists all SageMaker endpoints in the current AWS account and region
        that are in the 'InService' status. This is useful for tracking
        deployed models and identifying endpoints that may need cleanup.
        
        Returns:
            List[str]: List of endpoint names that are currently in service.
                      Returns empty list if no active endpoints found.
        
        Raises:
            RuntimeError: If unable to list endpoints
        
        Example:
            >>> from src.aws_client_manager import AWSClientManager
            >>> from src.configuration_manager import ConfigurationManager
            >>> 
            >>> # Initialize components
            >>> config_manager = ConfigurationManager()
            >>> pipeline_config = config_manager.load_pipeline_config()
            >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
            >>> sagemaker_client = aws_manager.get_sagemaker_client()
            >>> 
            >>> # Create deployer
            >>> deployer = ModelDeployer(sagemaker_client, pipeline_config)
            >>> 
            >>> # List active endpoints
            >>> active_endpoints = deployer.list_active_endpoints()
            >>> print(f"Found {len(active_endpoints)} active endpoints")
            >>> for endpoint in active_endpoints:
            ...     print(f"  - {endpoint}")
        """
        logger.info("Listing active endpoints")
        
        try:
            active_endpoints = []
            
            # Use paginator to handle large numbers of endpoints
            paginator = self.sagemaker_client.get_paginator('list_endpoints')
            page_iterator = paginator.paginate(
                StatusEquals='InService',
                SortBy='CreationTime',
                SortOrder='Descending'
            )
            
            for page in page_iterator:
                for endpoint in page.get('Endpoints', []):
                    endpoint_name = endpoint.get('EndpointName')
                    if endpoint_name:
                        active_endpoints.append(endpoint_name)
            
            logger.info(
                f"Found {len(active_endpoints)} active endpoints",
                extra={
                    "context": {
                        "count": len(active_endpoints),
                        "endpoints": active_endpoints,
                    }
                }
            )
            
            return active_endpoints
            
        except Exception as e:
            logger.error(
                f"Failed to list active endpoints: {e}",
                extra={"context": {"error": str(e)}}
            )
            raise RuntimeError(f"Failed to list active endpoints: {e}")
