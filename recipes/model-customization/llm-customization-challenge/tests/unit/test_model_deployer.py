"""
Unit tests for ModelDeployer class.

Tests cover:
- __init__ method with valid and invalid parameters
- SageMaker client initialization
- Configuration validation
- Error handling for missing or invalid inputs
- deploy_model() method with various scenarios
- delete_endpoint() method
- list_active_endpoints() method
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.model_deployer import ModelDeployer
from src.config_models import PipelineConfig, DeploymentResult


class TestModelDeployerInit:
    """Test suite for ModelDeployer.__init__ method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        mock_client = Mock()
        mock_client.create_model = Mock(return_value={})
        mock_client.create_endpoint_config = Mock(return_value={})
        mock_client.create_endpoint = Mock(return_value={
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint'
        })
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'InService',
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint',
            'CreationTime': datetime.now()
        })
        mock_client.delete_endpoint = Mock(return_value={})
        mock_client.delete_endpoint_config = Mock(return_value={})
        mock_client.delete_model = Mock(return_value={})
        mock_client.get_paginator = Mock()
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        return mock_client
    
    def test_init_with_valid_parameters(self, mock_sagemaker_client, valid_pipeline_config):
        """Test initialization with valid sagemaker_client and config"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        assert deployer.sagemaker_client is mock_sagemaker_client
        assert deployer.config is valid_pipeline_config
    
    def test_init_stores_sagemaker_client(self, mock_sagemaker_client, valid_pipeline_config):
        """Test that sagemaker_client is properly stored"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        assert hasattr(deployer, 'sagemaker_client')
        assert deployer.sagemaker_client is mock_sagemaker_client
    
    def test_init_stores_config(self, mock_sagemaker_client, valid_pipeline_config):
        """Test that config is properly stored"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        assert hasattr(deployer, 'config')
        assert deployer.config is valid_pipeline_config
    
    def test_init_with_none_sagemaker_client(self, valid_pipeline_config):
        """Test that None sagemaker_client raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            ModelDeployer(None, valid_pipeline_config)
        
        assert "sagemaker_client cannot be None" in str(exc_info.value)
    
    def test_init_with_none_config(self, mock_sagemaker_client):
        """Test that None config raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            ModelDeployer(mock_sagemaker_client, None)
        
        assert "config cannot be None" in str(exc_info.value)
    
    def test_init_with_both_none(self):
        """Test that both None parameters raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            ModelDeployer(None, None)
        
        # Should fail on sagemaker_client first
        assert "sagemaker_client cannot be None" in str(exc_info.value)
    
    def test_init_with_invalid_config_type(self, mock_sagemaker_client):
        """Test that non-PipelineConfig config raises TypeError"""
        invalid_config = {
            'aws_region': 'us-east-1',
            'sagemaker_role_arn': 'arn:aws:iam::123456789012:role/SageMakerRole'
        }
        
        with pytest.raises(TypeError) as exc_info:
            ModelDeployer(mock_sagemaker_client, invalid_config)
        
        assert "config must be a PipelineConfig instance" in str(exc_info.value)
        assert "dict" in str(exc_info.value)
    
    def test_init_with_string_config(self, mock_sagemaker_client):
        """Test that string config raises TypeError"""
        with pytest.raises(TypeError) as exc_info:
            ModelDeployer(mock_sagemaker_client, "not a config")
        
        assert "config must be a PipelineConfig instance" in str(exc_info.value)
        assert "str" in str(exc_info.value)

    def test_init_with_incomplete_config(self, mock_sagemaker_client):
        """Test that config missing required attributes raises AttributeError"""
        # Create a mock object that passes isinstance check but lacks attributes
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        
        # Remove required attributes
        del incomplete_config.sagemaker_role_arn
        del incomplete_config.inference_instance_type
        del incomplete_config.aws_region
        
        with pytest.raises(AttributeError) as exc_info:
            ModelDeployer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "sagemaker_role_arn" in error_msg
        assert "inference_instance_type" in error_msg
        assert "aws_region" in error_msg
    
    def test_init_with_config_missing_sagemaker_role_arn(self, mock_sagemaker_client):
        """Test that config without sagemaker_role_arn raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.inference_instance_type = "ml.g5.xlarge"
        incomplete_config.s3_bucket = "my-bucket"
        incomplete_config.base_model = "meta-llama/Llama-3.2-3B"
        incomplete_config.max_retries = 3
        incomplete_config.initial_backoff_seconds = 2
        incomplete_config.max_backoff_seconds = 60
        
        # Remove sagemaker_role_arn
        del incomplete_config.sagemaker_role_arn
        
        with pytest.raises(AttributeError) as exc_info:
            ModelDeployer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "sagemaker_role_arn" in error_msg
    
    def test_init_with_config_missing_inference_instance_type(self, mock_sagemaker_client):
        """Test that config without inference_instance_type raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        incomplete_config.s3_bucket = "my-bucket"
        incomplete_config.base_model = "meta-llama/Llama-3.2-3B"
        incomplete_config.max_retries = 3
        incomplete_config.initial_backoff_seconds = 2
        incomplete_config.max_backoff_seconds = 60
        
        # Remove inference_instance_type
        del incomplete_config.inference_instance_type
        
        with pytest.raises(AttributeError) as exc_info:
            ModelDeployer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "inference_instance_type" in error_msg
    
    def test_init_logs_initialization(self, mock_sagemaker_client, valid_pipeline_config, caplog):
        """Test that initialization is logged"""
        import logging
        caplog.set_level(logging.INFO)
        
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        # Check that initialization was logged
        assert any("ModelDeployer initialized" in record.message for record in caplog.records)
    
    def test_init_with_different_instance_types(self, mock_sagemaker_client):
        """Test initialization with various instance types"""
        instance_types = [
            "ml.g5.xlarge",
            "ml.g5.2xlarge",
            "ml.g5.4xlarge",
            "ml.p3.2xlarge",
            "ml.p4d.24xlarge"
        ]
        
        for instance_type in instance_types:
            config = PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type=instance_type,
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-finetuning-bucket"
            )
            
            deployer = ModelDeployer(mock_sagemaker_client, config)
            assert deployer.config.inference_instance_type == instance_type

    def test_init_with_different_regions(self, mock_sagemaker_client):
        """Test initialization with various AWS regions"""
        regions = [
            "us-east-1",
            "us-west-2",
            "eu-west-1",
            "ap-southeast-1"
        ]
        
        for region in regions:
            config = PipelineConfig(
                aws_region=region,
                bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-finetuning-bucket"
            )
            
            deployer = ModelDeployer(mock_sagemaker_client, config)
            assert deployer.config.aws_region == region
    
    def test_init_preserves_all_config_attributes(self, mock_sagemaker_client, valid_pipeline_config):
        """Test that all config attributes are accessible after initialization"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        # Verify all required attributes are accessible
        assert deployer.config.sagemaker_role_arn == valid_pipeline_config.sagemaker_role_arn
        assert deployer.config.inference_instance_type == valid_pipeline_config.inference_instance_type
        assert deployer.config.aws_region == valid_pipeline_config.aws_region
        assert deployer.config.s3_bucket == valid_pipeline_config.s3_bucket
        assert deployer.config.base_model == valid_pipeline_config.base_model
        assert deployer.config.max_retries == valid_pipeline_config.max_retries
        assert deployer.config.initial_backoff_seconds == valid_pipeline_config.initial_backoff_seconds
        assert deployer.config.max_backoff_seconds == valid_pipeline_config.max_backoff_seconds


class TestModelDeployerDeployModel:
    """Test suite for ModelDeployer.deploy_model() method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client with deployment responses"""
        mock_client = Mock()
        
        # Mock create_model
        mock_client.create_model = Mock(return_value={})
        
        # Mock create_endpoint_config
        mock_client.create_endpoint_config = Mock(return_value={})
        
        # Mock create_endpoint
        mock_client.create_endpoint = Mock(return_value={
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint'
        })
        
        # Mock describe_endpoint - return InService status
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'InService',
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint',
            'CreationTime': datetime.now()
        })
        
        # Mock exceptions
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        return mock_client

    def test_deploy_model_with_valid_inputs(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test deploy_model with valid inputs returns successful result"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        result = deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert isinstance(result, DeploymentResult)
        assert result.status == "InService"
        assert result.is_successful()
    
    def test_deploy_model_calls_create_model(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that deploy_model calls SageMaker create_model"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert mock_sagemaker_client.create_model.called
    
    def test_deploy_model_calls_create_endpoint_config(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that deploy_model calls SageMaker create_endpoint_config"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert mock_sagemaker_client.create_endpoint_config.called
    
    def test_deploy_model_calls_create_endpoint(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that deploy_model calls SageMaker create_endpoint"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert mock_sagemaker_client.create_endpoint.called
    
    def test_deploy_model_with_empty_model_artifact_uri(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that deploy_model raises ValueError for empty model_artifact_uri"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            deployer.deploy_model(
                model_artifact_uri="",
                endpoint_name="test-endpoint"
            )
        
        assert "model_artifact_uri cannot be empty" in str(exc_info.value)
    
    def test_deploy_model_with_empty_endpoint_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that deploy_model raises ValueError for empty endpoint_name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            deployer.deploy_model(
                model_artifact_uri="s3://bucket/model.tar.gz",
                endpoint_name=""
            )
        
        assert "endpoint_name cannot be empty" in str(exc_info.value)
    
    def test_deploy_model_returns_deployment_result(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that deploy_model returns a DeploymentResult object"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        result = deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert isinstance(result, DeploymentResult)
        assert hasattr(result, 'endpoint_name')
        assert hasattr(result, 'endpoint_arn')
        assert hasattr(result, 'status')
        assert hasattr(result, 'creation_time')
    
    def test_deploy_model_with_failed_deployment(
        self,
        valid_pipeline_config
    ):
        """Test deploy_model handles failed deployment"""
        mock_client = Mock()
        mock_client.create_model = Mock(return_value={})
        mock_client.create_endpoint_config = Mock(return_value={})
        mock_client.create_endpoint = Mock(return_value={
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint'
        })
        
        # Mock failed deployment
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'Failed',
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint',
            'CreationTime': datetime.now(),
            'FailureReason': 'Insufficient capacity'
        })
        
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert result.status == "Failed"
        assert not result.is_successful()
        assert result.error_message is not None
        assert "capacity" in result.error_message.lower()

    def test_deploy_model_logs_progress(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        caplog
    ):
        """Test that deploy_model logs progress messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        # Check for key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Starting model deployment" in msg for msg in log_messages)
        assert any("Deployment completed successfully" in msg or "InService" in msg for msg in log_messages)
    
    def test_deploy_model_with_create_model_failure(
        self,
        valid_pipeline_config
    ):
        """Test deploy_model handles create_model failure"""
        mock_client = Mock()
        mock_client.create_model = Mock(side_effect=Exception("Model creation failed"))
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        with pytest.raises(RuntimeError) as exc_info:
            deployer.deploy_model(
                model_artifact_uri="s3://bucket/model.tar.gz",
                endpoint_name="test-endpoint"
            )
        
        assert "Failed to create SageMaker model" in str(exc_info.value)
    
    def test_deploy_model_with_create_endpoint_config_failure(
        self,
        valid_pipeline_config
    ):
        """Test deploy_model handles create_endpoint_config failure"""
        mock_client = Mock()
        mock_client.create_model = Mock(return_value={})
        mock_client.create_endpoint_config = Mock(side_effect=Exception("Config creation failed"))
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        with pytest.raises(RuntimeError) as exc_info:
            deployer.deploy_model(
                model_artifact_uri="s3://bucket/model.tar.gz",
                endpoint_name="test-endpoint"
            )
        
        assert "Failed to create endpoint configuration" in str(exc_info.value)
    
    def test_deploy_model_with_create_endpoint_failure(
        self,
        valid_pipeline_config
    ):
        """Test deploy_model handles create_endpoint failure"""
        mock_client = Mock()
        mock_client.create_model = Mock(return_value={})
        mock_client.create_endpoint_config = Mock(return_value={})
        mock_client.create_endpoint = Mock(side_effect=Exception("Endpoint creation failed"))
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        with pytest.raises(RuntimeError) as exc_info:
            deployer.deploy_model(
                model_artifact_uri="s3://bucket/model.tar.gz",
                endpoint_name="test-endpoint"
            )
        
        assert "Failed to create endpoint" in str(exc_info.value)


class TestModelDeployerDeleteEndpoint:
    """Test suite for ModelDeployer.delete_endpoint() method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client with deletion responses"""
        mock_client = Mock()
        
        # Mock delete operations
        mock_client.delete_endpoint = Mock(return_value={})
        mock_client.delete_endpoint_config = Mock(return_value={})
        mock_client.delete_model = Mock(return_value={})
        
        # Mock exceptions
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        return mock_client

    def test_delete_endpoint_with_valid_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test delete_endpoint with valid endpoint name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        # Should not raise any exception
        deployer.delete_endpoint("test-endpoint")
        
        # Verify all delete methods were called
        assert mock_sagemaker_client.delete_endpoint.called
        assert mock_sagemaker_client.delete_endpoint_config.called
        assert mock_sagemaker_client.delete_model.called
    
    def test_delete_endpoint_calls_delete_endpoint(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that delete_endpoint calls SageMaker delete_endpoint"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.delete_endpoint("test-endpoint")
        
        mock_sagemaker_client.delete_endpoint.assert_called_once_with(
            EndpointName="test-endpoint"
        )
    
    def test_delete_endpoint_calls_delete_endpoint_config(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that delete_endpoint calls SageMaker delete_endpoint_config"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.delete_endpoint("test-endpoint")
        
        mock_sagemaker_client.delete_endpoint_config.assert_called_once_with(
            EndpointConfigName="test-endpoint-config"
        )
    
    def test_delete_endpoint_calls_delete_model(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that delete_endpoint calls SageMaker delete_model"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.delete_endpoint("test-endpoint")
        
        mock_sagemaker_client.delete_model.assert_called_once_with(
            ModelName="test-endpoint-model"
        )
    
    def test_delete_endpoint_with_empty_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that delete_endpoint raises ValueError for empty endpoint_name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            deployer.delete_endpoint("")
        
        assert "endpoint_name cannot be None or empty" in str(exc_info.value)
    
    def test_delete_endpoint_with_none_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that delete_endpoint raises ValueError for None endpoint_name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            deployer.delete_endpoint(None)
        
        assert "endpoint_name cannot be None or empty" in str(exc_info.value)
    
    def test_delete_endpoint_handles_resource_not_found(
        self,
        valid_pipeline_config
    ):
        """Test that delete_endpoint handles ResourceNotFound gracefully"""
        mock_client = Mock()
        
        # Mock ResourceNotFound exception
        ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = ResourceNotFound
        
        # Endpoint not found
        mock_client.delete_endpoint = Mock(side_effect=ResourceNotFound())
        mock_client.delete_endpoint_config = Mock(return_value={})
        mock_client.delete_model = Mock(return_value={})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        # Should not raise exception
        deployer.delete_endpoint("test-endpoint")
        
        # Should still try to delete config and model
        assert mock_client.delete_endpoint_config.called
        assert mock_client.delete_model.called
    
    def test_delete_endpoint_continues_on_partial_failure(
        self,
        valid_pipeline_config
    ):
        """Test that delete_endpoint continues even if some deletions fail"""
        mock_client = Mock()
        
        # Mock exceptions
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        # Endpoint deletion fails
        mock_client.delete_endpoint = Mock(side_effect=Exception("Deletion failed"))
        mock_client.delete_endpoint_config = Mock(return_value={})
        mock_client.delete_model = Mock(return_value={})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        # Should not raise exception
        deployer.delete_endpoint("test-endpoint")
        
        # Should still try to delete config and model
        assert mock_client.delete_endpoint_config.called
        assert mock_client.delete_model.called
    
    def test_delete_endpoint_logs_operations(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        caplog
    ):
        """Test that delete_endpoint logs deletion operations"""
        import logging
        caplog.set_level(logging.INFO)
        
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer.delete_endpoint("test-endpoint")
        
        # Check for key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Starting endpoint deletion" in msg for msg in log_messages)
        assert any("Endpoint deletion completed" in msg for msg in log_messages)



class TestModelDeployerListActiveEndpoints:
    """Test suite for ModelDeployer.list_active_endpoints() method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client_with_endpoints(self):
        """Create a mock SageMaker client with endpoint listing"""
        mock_client = Mock()
        
        # Mock paginator
        mock_paginator = Mock()
        mock_page_iterator = [
            {
                'Endpoints': [
                    {'EndpointName': 'endpoint-1', 'EndpointStatus': 'InService'},
                    {'EndpointName': 'endpoint-2', 'EndpointStatus': 'InService'},
                ]
            },
            {
                'Endpoints': [
                    {'EndpointName': 'endpoint-3', 'EndpointStatus': 'InService'},
                ]
            }
        ]
        mock_paginator.paginate = Mock(return_value=mock_page_iterator)
        mock_client.get_paginator = Mock(return_value=mock_paginator)
        
        # Mock exceptions
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        return mock_client
    
    def test_list_active_endpoints_returns_list(
        self,
        mock_sagemaker_client_with_endpoints,
        valid_pipeline_config
    ):
        """Test list_active_endpoints returns a list"""
        deployer = ModelDeployer(mock_sagemaker_client_with_endpoints, valid_pipeline_config)
        
        result = deployer.list_active_endpoints()
        
        assert isinstance(result, list)
    
    def test_list_active_endpoints_returns_endpoint_names(
        self,
        mock_sagemaker_client_with_endpoints,
        valid_pipeline_config
    ):
        """Test list_active_endpoints returns correct endpoint names"""
        deployer = ModelDeployer(mock_sagemaker_client_with_endpoints, valid_pipeline_config)
        
        result = deployer.list_active_endpoints()
        
        assert len(result) == 3
        assert 'endpoint-1' in result
        assert 'endpoint-2' in result
        assert 'endpoint-3' in result
    
    def test_list_active_endpoints_with_no_endpoints(
        self,
        valid_pipeline_config
    ):
        """Test list_active_endpoints with no endpoints"""
        mock_client = Mock()
        
        # Mock paginator with empty results
        mock_paginator = Mock()
        mock_page_iterator = [{'Endpoints': []}]
        mock_paginator.paginate = Mock(return_value=mock_page_iterator)
        mock_client.get_paginator = Mock(return_value=mock_paginator)
        
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer.list_active_endpoints()
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_list_active_endpoints_calls_get_paginator(
        self,
        mock_sagemaker_client_with_endpoints,
        valid_pipeline_config
    ):
        """Test that list_active_endpoints calls get_paginator"""
        deployer = ModelDeployer(mock_sagemaker_client_with_endpoints, valid_pipeline_config)
        
        deployer.list_active_endpoints()
        
        mock_sagemaker_client_with_endpoints.get_paginator.assert_called_once_with('list_endpoints')
    
    def test_list_active_endpoints_handles_api_error(
        self,
        valid_pipeline_config
    ):
        """Test that list_active_endpoints handles API errors"""
        mock_client = Mock()
        mock_client.get_paginator = Mock(side_effect=Exception("API error"))
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        with pytest.raises(RuntimeError) as exc_info:
            deployer.list_active_endpoints()
        
        assert "Failed to list active endpoints" in str(exc_info.value)
    
    def test_list_active_endpoints_logs_results(
        self,
        mock_sagemaker_client_with_endpoints,
        valid_pipeline_config,
        caplog
    ):
        """Test that list_active_endpoints logs results"""
        import logging
        caplog.set_level(logging.INFO)
        
        deployer = ModelDeployer(mock_sagemaker_client_with_endpoints, valid_pipeline_config)
        
        deployer.list_active_endpoints()
        
        # Check for key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Listing active endpoints" in msg for msg in log_messages)
        assert any("Found" in msg and "active endpoints" in msg for msg in log_messages)


class TestModelDeployerWaitForDeployment:
    """Test suite for ModelDeployer._wait_for_deployment() method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    def test_wait_for_deployment_with_immediate_success(
        self,
        valid_pipeline_config
    ):
        """Test _wait_for_deployment when endpoint is immediately InService"""
        mock_client = Mock()
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'InService',
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test',
            'CreationTime': datetime.now()
        })
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer._wait_for_deployment("test-endpoint", poll_interval=1)
        
        assert result.status == "InService"
        assert result.is_successful()
    
    def test_wait_for_deployment_with_eventual_success(
        self,
        valid_pipeline_config
    ):
        """Test _wait_for_deployment when endpoint eventually becomes InService"""
        mock_client = Mock()
        
        # Mock multiple status checks
        status_sequence = [
            {'EndpointStatus': 'Creating', 'EndpointArn': 'arn:test', 'CreationTime': datetime.now()},
            {'EndpointStatus': 'Creating', 'EndpointArn': 'arn:test', 'CreationTime': datetime.now()},
            {'EndpointStatus': 'InService', 'EndpointArn': 'arn:test', 'CreationTime': datetime.now()}
        ]
        mock_client.describe_endpoint = Mock(side_effect=status_sequence)
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer._wait_for_deployment("test-endpoint", poll_interval=0.1)
        
        assert result.status == "InService"
        assert result.is_successful()
        assert mock_client.describe_endpoint.call_count == 3
    
    def test_wait_for_deployment_with_failure(
        self,
        valid_pipeline_config
    ):
        """Test _wait_for_deployment when endpoint fails"""
        mock_client = Mock()
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'Failed',
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test',
            'CreationTime': datetime.now(),
            'FailureReason': 'Insufficient capacity'
        })
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer._wait_for_deployment("test-endpoint", poll_interval=1)
        
        assert result.status == "Failed"
        assert not result.is_successful()
        assert "capacity" in result.error_message.lower()
    
    def test_wait_for_deployment_handles_describe_error(
        self,
        valid_pipeline_config
    ):
        """Test _wait_for_deployment handles describe_endpoint errors"""
        mock_client = Mock()
        mock_client.describe_endpoint = Mock(side_effect=Exception("API error"))
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        with pytest.raises(RuntimeError) as exc_info:
            deployer._wait_for_deployment("test-endpoint", poll_interval=1)
        
        assert "Failed to monitor endpoint deployment" in str(exc_info.value)



class TestModelDeployerCreateModel:
    """Test suite for ModelDeployer._create_model() method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        mock_client = Mock()
        mock_client.create_model = Mock(return_value={})
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        return mock_client
    
    def test_create_model_calls_sagemaker_create_model(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _create_model calls SageMaker create_model API"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer._create_model("test-model", "s3://bucket/model.tar.gz")
        
        assert mock_sagemaker_client.create_model.called
    
    def test_create_model_with_correct_parameters(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _create_model passes correct parameters"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer._create_model("test-model", "s3://bucket/model.tar.gz")
        
        call_args = mock_sagemaker_client.create_model.call_args
        assert call_args[1]['ModelName'] == "test-model"
        assert call_args[1]['PrimaryContainer']['ModelDataUrl'] == "s3://bucket/model.tar.gz"
        assert call_args[1]['ExecutionRoleArn'] == valid_pipeline_config.sagemaker_role_arn
    
    def test_create_model_includes_inference_image(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _create_model includes inference image"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer._create_model("test-model", "s3://bucket/model.tar.gz")
        
        call_args = mock_sagemaker_client.create_model.call_args
        assert 'Image' in call_args[1]['PrimaryContainer']
        assert call_args[1]['PrimaryContainer']['Image'] is not None
    
    def test_create_model_handles_api_error(
        self,
        valid_pipeline_config
    ):
        """Test that _create_model propagates API errors"""
        mock_client = Mock()
        mock_client.create_model = Mock(side_effect=Exception("Model creation failed"))
        mock_client.exceptions = Mock()
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        with pytest.raises(Exception) as exc_info:
            deployer._create_model("test-model", "s3://bucket/model.tar.gz")
        
        assert "Model creation failed" in str(exc_info.value)
    
    def test_create_model_with_different_model_names(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test _create_model with various model names"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        model_names = [
            "customer-support-model",
            "code-review-model",
            "test-endpoint-123-model"
        ]
        
        for model_name in model_names:
            mock_sagemaker_client.create_model.reset_mock()
            deployer._create_model(model_name, "s3://bucket/model.tar.gz")
            
            call_args = mock_sagemaker_client.create_model.call_args
            assert call_args[1]['ModelName'] == model_name


class TestModelDeployerCreateEndpointConfig:
    """Test suite for ModelDeployer._create_endpoint_config() method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        mock_client = Mock()
        mock_client.create_endpoint_config = Mock(return_value={})
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        return mock_client
    
    def test_create_endpoint_config_calls_sagemaker_api(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _create_endpoint_config calls SageMaker API"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer._create_endpoint_config("test-config", "test-model")
        
        assert mock_sagemaker_client.create_endpoint_config.called
    
    def test_create_endpoint_config_with_correct_parameters(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _create_endpoint_config passes correct parameters"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer._create_endpoint_config("test-config", "test-model")
        
        call_args = mock_sagemaker_client.create_endpoint_config.call_args
        assert call_args[1]['EndpointConfigName'] == "test-config"
        assert len(call_args[1]['ProductionVariants']) == 1
        assert call_args[1]['ProductionVariants'][0]['ModelName'] == "test-model"
    
    def test_create_endpoint_config_uses_configured_instance_type(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _create_endpoint_config uses configured instance type"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer._create_endpoint_config("test-config", "test-model")
        
        call_args = mock_sagemaker_client.create_endpoint_config.call_args
        variant = call_args[1]['ProductionVariants'][0]
        assert variant['InstanceType'] == valid_pipeline_config.inference_instance_type
    
    def test_create_endpoint_config_sets_initial_instance_count(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _create_endpoint_config sets initial instance count to 1"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        deployer._create_endpoint_config("test-config", "test-model")
        
        call_args = mock_sagemaker_client.create_endpoint_config.call_args
        variant = call_args[1]['ProductionVariants'][0]
        assert variant['InitialInstanceCount'] == 1
    
    def test_create_endpoint_config_handles_api_error(
        self,
        valid_pipeline_config
    ):
        """Test that _create_endpoint_config propagates API errors"""
        mock_client = Mock()
        mock_client.create_endpoint_config = Mock(side_effect=Exception("Config creation failed"))
        mock_client.exceptions = Mock()
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        with pytest.raises(Exception) as exc_info:
            deployer._create_endpoint_config("test-config", "test-model")
        
        assert "Config creation failed" in str(exc_info.value)


class TestModelDeployerGetInferenceImage:
    """Test suite for ModelDeployer._get_inference_image() method"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        mock_client = Mock()
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        return mock_client
    
    def test_get_inference_image_returns_string(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _get_inference_image returns a string"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        result = deployer._get_inference_image()
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_get_inference_image_includes_base_model(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _get_inference_image includes base model reference"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        result = deployer._get_inference_image()
        
        # Should reference the base model in some way
        assert valid_pipeline_config.base_model in result or "inference" in result.lower()


class TestModelDeployerEndToEnd:
    """End-to-end test suite for ModelDeployer with complete deployment flow"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client_full(self):
        """Create a fully mocked SageMaker client for end-to-end testing"""
        mock_client = Mock()
        
        # Mock all create operations
        mock_client.create_model = Mock(return_value={})
        mock_client.create_endpoint_config = Mock(return_value={})
        mock_client.create_endpoint = Mock(return_value={
            'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint'
        })
        
        # Mock describe_endpoint with progression
        status_sequence = [
            {'EndpointStatus': 'Creating', 'EndpointArn': 'arn:test', 'CreationTime': datetime.now()},
            {'EndpointStatus': 'InService', 'EndpointArn': 'arn:test', 'CreationTime': datetime.now()}
        ]
        mock_client.describe_endpoint = Mock(side_effect=status_sequence)
        
        # Mock delete operations
        mock_client.delete_endpoint = Mock(return_value={})
        mock_client.delete_endpoint_config = Mock(return_value={})
        mock_client.delete_model = Mock(return_value={})
        
        # Mock list operations
        mock_paginator = Mock()
        mock_page_iterator = [
            {
                'Endpoints': [
                    {'EndpointName': 'test-endpoint', 'EndpointStatus': 'InService'},
                ]
            }
        ]
        mock_paginator.paginate = Mock(return_value=mock_page_iterator)
        mock_client.get_paginator = Mock(return_value=mock_paginator)
        
        # Mock exceptions
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        return mock_client
    
    def test_full_deployment_lifecycle(
        self,
        mock_sagemaker_client_full,
        valid_pipeline_config
    ):
        """Test complete deployment and cleanup lifecycle"""
        deployer = ModelDeployer(mock_sagemaker_client_full, valid_pipeline_config)
        
        # Deploy model
        result = deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert result.is_successful()
        assert result.endpoint_name == "test-endpoint"
        
        # List active endpoints
        endpoints = deployer.list_active_endpoints()
        assert "test-endpoint" in endpoints
        
        # Delete endpoint
        deployer.delete_endpoint("test-endpoint")
        
        # Verify all operations were called
        assert mock_sagemaker_client_full.create_model.called
        assert mock_sagemaker_client_full.create_endpoint_config.called
        assert mock_sagemaker_client_full.create_endpoint.called
        assert mock_sagemaker_client_full.delete_endpoint.called
        assert mock_sagemaker_client_full.delete_endpoint_config.called
        assert mock_sagemaker_client_full.delete_model.called
    
    def test_deployment_with_multiple_endpoints(
        self,
        mock_sagemaker_client_full,
        valid_pipeline_config
    ):
        """Test deploying multiple endpoints"""
        deployer = ModelDeployer(mock_sagemaker_client_full, valid_pipeline_config)
        
        endpoints_to_deploy = [
            ("endpoint-1", "s3://bucket/model1.tar.gz"),
            ("endpoint-2", "s3://bucket/model2.tar.gz"),
            ("endpoint-3", "s3://bucket/model3.tar.gz"),
        ]
        
        results = []
        for endpoint_name, model_uri in endpoints_to_deploy:
            # Reset mock for each deployment
            mock_sagemaker_client_full.describe_endpoint.side_effect = [
                {'EndpointStatus': 'Creating', 'EndpointArn': f'arn:{endpoint_name}', 'CreationTime': datetime.now()},
                {'EndpointStatus': 'InService', 'EndpointArn': f'arn:{endpoint_name}', 'CreationTime': datetime.now()}
            ]
            
            result = deployer.deploy_model(
                model_artifact_uri=model_uri,
                endpoint_name=endpoint_name
            )
            results.append(result)
        
        # Verify all deployments succeeded
        assert all(r.is_successful() for r in results)
        assert len(results) == 3
    
    def test_deployment_error_recovery(
        self,
        valid_pipeline_config
    ):
        """Test error handling and recovery during deployment"""
        mock_client = Mock()
        
        # First attempt fails, second succeeds
        mock_client.create_model = Mock(side_effect=[
            Exception("Transient error"),
            {}
        ])
        mock_client.create_endpoint_config = Mock(return_value={})
        mock_client.create_endpoint = Mock(return_value={
            'EndpointArn': 'arn:test'
        })
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'InService',
            'EndpointArn': 'arn:test',
            'CreationTime': datetime.now()
        })
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        # First attempt should fail
        with pytest.raises(RuntimeError):
            deployer.deploy_model(
                model_artifact_uri="s3://bucket/model.tar.gz",
                endpoint_name="test-endpoint"
            )
        
        # Second attempt should succeed
        result = deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint"
        )
        
        assert result.is_successful()


class TestModelDeployerEdgeCases:
    """Test suite for edge cases and boundary conditions"""
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Create a valid PipelineConfig for testing"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        mock_client = Mock()
        mock_client.create_model = Mock(return_value={})
        mock_client.create_endpoint_config = Mock(return_value={})
        mock_client.create_endpoint = Mock(return_value={
            'EndpointArn': 'arn:test'
        })
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'InService',
            'EndpointArn': 'arn:test',
            'CreationTime': datetime.now()
        })
        mock_client.delete_endpoint = Mock(return_value={})
        mock_client.delete_endpoint_config = Mock(return_value={})
        mock_client.delete_model = Mock(return_value={})
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        return mock_client
    
    def test_deploy_model_with_whitespace_only_model_uri(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test deploy_model with whitespace-only model_artifact_uri"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            deployer.deploy_model(
                model_artifact_uri="   ",
                endpoint_name="test-endpoint"
            )
        
        assert "model_artifact_uri cannot be empty" in str(exc_info.value)
    
    def test_deploy_model_with_whitespace_only_endpoint_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test deploy_model with whitespace-only endpoint_name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            deployer.deploy_model(
                model_artifact_uri="s3://bucket/model.tar.gz",
                endpoint_name="   "
            )
        
        assert "endpoint_name cannot be empty" in str(exc_info.value)
    
    def test_delete_endpoint_with_whitespace_only_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test delete_endpoint with whitespace-only endpoint_name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            deployer.delete_endpoint("   ")
        
        assert "endpoint_name cannot be None or empty" in str(exc_info.value)
    
    def test_deploy_model_with_very_long_endpoint_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test deploy_model with very long endpoint name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        long_name = "a" * 100
        
        result = deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name=long_name
        )
        
        assert result.is_successful()
    
    def test_deploy_model_with_special_characters_in_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test deploy_model with special characters in endpoint name"""
        deployer = ModelDeployer(mock_sagemaker_client, valid_pipeline_config)
        
        # SageMaker allows hyphens and alphanumeric
        special_name = "test-endpoint-123"
        
        result = deployer.deploy_model(
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name=special_name
        )
        
        assert result.is_successful()
    
    def test_wait_for_deployment_with_rolling_back_status(
        self,
        valid_pipeline_config
    ):
        """Test _wait_for_deployment handles RollingBack status"""
        mock_client = Mock()
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'RollingBack',
            'EndpointArn': 'arn:test',
            'CreationTime': datetime.now(),
            'FailureReason': 'Deployment rollback initiated'
        })
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer._wait_for_deployment("test-endpoint", poll_interval=1)
        
        assert result.status == "RollingBack"
        assert not result.is_successful()
    
    def test_wait_for_deployment_with_system_updating_status(
        self,
        valid_pipeline_config
    ):
        """Test _wait_for_deployment handles SystemUpdating status"""
        mock_client = Mock()
        mock_client.describe_endpoint = Mock(return_value={
            'EndpointStatus': 'SystemUpdating',
            'EndpointArn': 'arn:test',
            'CreationTime': datetime.now(),
            'FailureReason': 'System update in progress'
        })
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer._wait_for_deployment("test-endpoint", poll_interval=1)
        
        assert result.status == "SystemUpdating"
        assert not result.is_successful()
    
    def test_delete_endpoint_all_resources_already_deleted(
        self,
        valid_pipeline_config
    ):
        """Test delete_endpoint when all resources are already deleted"""
        mock_client = Mock()
        
        ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = ResourceNotFound
        
        # All delete operations raise ResourceNotFound
        mock_client.delete_endpoint = Mock(side_effect=ResourceNotFound())
        mock_client.delete_endpoint_config = Mock(side_effect=ResourceNotFound())
        mock_client.delete_model = Mock(side_effect=ResourceNotFound())
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        # Should not raise exception
        deployer.delete_endpoint("test-endpoint")
        
        # All delete methods should have been called
        assert mock_client.delete_endpoint.called
        assert mock_client.delete_endpoint_config.called
        assert mock_client.delete_model.called
    
    def test_list_active_endpoints_with_pagination(
        self,
        valid_pipeline_config
    ):
        """Test list_active_endpoints with multiple pages"""
        mock_client = Mock()
        
        # Mock paginator with multiple pages
        mock_paginator = Mock()
        mock_page_iterator = [
            {
                'Endpoints': [
                    {'EndpointName': f'endpoint-{i}', 'EndpointStatus': 'InService'}
                    for i in range(10)
                ]
            },
            {
                'Endpoints': [
                    {'EndpointName': f'endpoint-{i}', 'EndpointStatus': 'InService'}
                    for i in range(10, 15)
                ]
            }
        ]
        mock_paginator.paginate = Mock(return_value=mock_page_iterator)
        mock_client.get_paginator = Mock(return_value=mock_paginator)
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        deployer = ModelDeployer(mock_client, valid_pipeline_config)
        
        result = deployer.list_active_endpoints()
        
        # Should have all 15 endpoints
        assert len(result) == 15
        assert 'endpoint-0' in result
        assert 'endpoint-14' in result
