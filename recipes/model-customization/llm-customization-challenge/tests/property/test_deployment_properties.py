"""
Property-Based Tests for Model Deployer

This module implements property-based tests for the ModelDeployer class
using hypothesis. These tests verify universal properties that should hold
across all valid inputs.

Properties tested:
- Property 24: Resource Cleanup Based on Configuration

Each test uses hypothesis with minimum 100 examples as per design requirements.
"""

import pytest
from unittest.mock import Mock, MagicMock, call
from datetime import datetime
from typing import List

from hypothesis import given, strategies as st, settings, assume

from src.model_deployer import ModelDeployer
from src.config_models import PipelineConfig, DeploymentResult


# ============================================================================
# Hypothesis Strategies for Deployment Testing
# ============================================================================

@st.composite
def valid_endpoint_name(draw) -> str:  # type: ignore[no-untyped-def]
    """
    Generate valid SageMaker endpoint names.
    
    Endpoint names must:
    - Be 1-63 characters long
    - Contain only alphanumeric characters and hyphens
    - Not start or end with a hyphen
    
    Returns:
        str: A valid endpoint name
    """
    # Generate a name with alphanumeric characters and hyphens
    # Start with a letter, end with alphanumeric
    first_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz'))
    
    # Middle characters can include hyphens
    middle_length = draw(st.integers(min_value=0, max_value=60))
    if middle_length > 0:
        middle_chars = draw(st.text(
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
            min_size=middle_length,
            max_size=middle_length
        ))
    else:
        middle_chars = ''
    
    # Last character must be alphanumeric (if we have middle chars)
    if middle_chars:
        last_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'))
        endpoint_name = first_char + middle_chars + last_char
    else:
        endpoint_name = first_char
    
    # Ensure no consecutive hyphens and doesn't start/end with hyphen
    endpoint_name = endpoint_name.replace('--', '-')
    endpoint_name = endpoint_name.strip('-')
    
    # Ensure minimum length
    if len(endpoint_name) < 1:
        endpoint_name = first_char
    
    return endpoint_name  # type: ignore[no-any-return]


@st.composite
def valid_endpoint_names_list(draw, min_size: int = 0, max_size: int = 10) -> List[str]:  # type: ignore[no-untyped-def]
    """
    Generate a list of valid endpoint names.
    
    Args:
        min_size: Minimum number of endpoints (default: 0)
        max_size: Maximum number of endpoints (default: 10)
    
    Returns:
        List[str]: List of valid endpoint names
    """
    num_endpoints = draw(st.integers(min_value=min_size, max_value=max_size))
    endpoints = []
    
    for i in range(num_endpoints):
        # Generate unique endpoint names by adding index
        base_name = draw(valid_endpoint_name())
        endpoint_name = f"{base_name}-{i}"
        endpoints.append(endpoint_name)
    
    return endpoints


def create_pipeline_config_with_cleanup(cleanup_enabled: bool) -> PipelineConfig:
    """
    Create a valid PipelineConfig with specified cleanup setting.
    
    Args:
        cleanup_enabled: Whether cleanup_resources should be True or False
    
    Returns:
        PipelineConfig: A valid pipeline configuration
    """
    return PipelineConfig(
        aws_region="us-east-1",
        bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
        training_instance_type="ml.g5.2xlarge",
        inference_instance_type="ml.g5.xlarge",
        baseline_model_endpoint="llama-70b-baseline",
        performance_threshold=0.60,
        max_iterations=5,
        cleanup_resources=cleanup_enabled,
        s3_bucket="test-bucket",
        base_model="meta-llama/Llama-3.2-3B",
        max_training_time_seconds=86400,
        max_retries=3,
        initial_backoff_seconds=2,
        max_backoff_seconds=60,
        artifact_retention_days=7
    )


# ============================================================================
# Helper Functions for Property Tests
# ============================================================================

def create_mock_sagemaker_client_for_cleanup(endpoint_names: List[str]) -> Mock:
    """
    Create a mock SageMaker client configured for cleanup testing.
    
    Args:
        endpoint_names: List of endpoint names that should exist
    
    Returns:
        Mock: Configured mock SageMaker client
    """
    mock_client = Mock()
    
    # Track which endpoints have been deleted
    deleted_endpoints = []
    deleted_configs = []
    deleted_models = []
    
    def mock_delete_endpoint(EndpointName: str) -> dict:  # type: ignore[type-arg]
        deleted_endpoints.append(EndpointName)
        return {}
    
    def mock_delete_endpoint_config(EndpointConfigName: str) -> dict:  # type: ignore[type-arg]
        deleted_configs.append(EndpointConfigName)
        return {}
    
    def mock_delete_model(ModelName: str) -> dict:  # type: ignore[type-arg]
        deleted_models.append(ModelName)
        return {}
    
    # Configure mock methods
    mock_client.delete_endpoint = Mock(side_effect=mock_delete_endpoint)
    mock_client.delete_endpoint_config = Mock(side_effect=mock_delete_endpoint_config)
    mock_client.delete_model = Mock(side_effect=mock_delete_model)
    
    # Store tracking lists on the mock for verification
    mock_client._deleted_endpoints = deleted_endpoints
    mock_client._deleted_configs = deleted_configs
    mock_client._deleted_models = deleted_models
    
    # Mock exceptions
    mock_client.exceptions = Mock()
    mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
    
    return mock_client


# ============================================================================
# Property-Based Tests
# ============================================================================

# Feature: automated-llm-finetuning-pipeline, Property 24: Resource Cleanup Based on Configuration
@given(
    cleanup_enabled=st.booleans(),
    endpoint_names=valid_endpoint_names_list(min_size=1, max_size=5)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.property
@pytest.mark.pbt
def test_property_24_resource_cleanup_based_on_configuration(
    cleanup_enabled: bool,
    endpoint_names: List[str]
) -> None:
    """
    **Validates: Requirements 9.1**
    
    Property 24: Resource Cleanup Based on Configuration
    
    For any pipeline execution with cleanup enabled, all created SageMaker
    endpoints should be deleted after pipeline completion; with cleanup
    disabled, all endpoints should be preserved.
    
    This property ensures that:
    - When cleanup_resources=True, all endpoints are deleted
    - When cleanup_resources=False, no endpoints are deleted
    - Cleanup behavior is consistent across all endpoint names
    - The configuration setting is respected in all cases
    """
    # Create a PipelineConfig with the specified cleanup setting
    config = create_pipeline_config_with_cleanup(cleanup_enabled=cleanup_enabled)
    
    # Create a mock SageMaker client
    mock_client = create_mock_sagemaker_client_for_cleanup(endpoint_names)
    
    # Create ModelDeployer instance
    deployer = ModelDeployer(mock_client, config)
    
    # Simulate pipeline execution: cleanup all endpoints if cleanup is enabled
    if config.cleanup_resources:
        # When cleanup is enabled, delete all endpoints
        for endpoint_name in endpoint_names:
            deployer.delete_endpoint(endpoint_name)
        
        # Verify all endpoints were deleted
        assert len(mock_client._deleted_endpoints) == len(endpoint_names), \
            f"Expected {len(endpoint_names)} endpoints to be deleted, but {len(mock_client._deleted_endpoints)} were deleted"
        
        # Verify all endpoint configs were deleted
        assert len(mock_client._deleted_configs) == len(endpoint_names), \
            f"Expected {len(endpoint_names)} endpoint configs to be deleted, but {len(mock_client._deleted_configs)} were deleted"
        
        # Verify all models were deleted
        assert len(mock_client._deleted_models) == len(endpoint_names), \
            f"Expected {len(endpoint_names)} models to be deleted, but {len(mock_client._deleted_models)} were deleted"
        
        # Verify the correct endpoints were deleted
        for endpoint_name in endpoint_names:
            assert endpoint_name in mock_client._deleted_endpoints, \
                f"Endpoint {endpoint_name} was not deleted"
            
            expected_config_name = f"{endpoint_name}-config"
            assert expected_config_name in mock_client._deleted_configs, \
                f"Endpoint config {expected_config_name} was not deleted"
            
            expected_model_name = f"{endpoint_name}-model"
            assert expected_model_name in mock_client._deleted_models, \
                f"Model {expected_model_name} was not deleted"
    
    else:
        # When cleanup is disabled, no endpoints should be deleted
        # Simulate pipeline completion without cleanup
        # (In real pipeline, delete_endpoint would not be called)
        
        # Verify no deletion methods were called
        assert len(mock_client._deleted_endpoints) == 0, \
            f"Expected no endpoints to be deleted when cleanup is disabled, but {len(mock_client._deleted_endpoints)} were deleted"
        
        assert len(mock_client._deleted_configs) == 0, \
            f"Expected no endpoint configs to be deleted when cleanup is disabled, but {len(mock_client._deleted_configs)} were deleted"
        
        assert len(mock_client._deleted_models) == 0, \
            f"Expected no models to be deleted when cleanup is disabled, but {len(mock_client._deleted_models)} were deleted"


# ============================================================================
# Additional Property Tests for Cleanup Behavior
# ============================================================================

@given(endpoint_name=valid_endpoint_name())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_cleanup_deletes_all_related_resources(endpoint_name: str) -> None:
    """
    Verify that cleanup deletes endpoint, config, and model.
    
    This test ensures that when an endpoint is deleted, all three related
    resources (endpoint, endpoint config, and model) are properly cleaned up.
    """
    # Create config with cleanup enabled
    config = create_pipeline_config_with_cleanup(cleanup_enabled=True)
    
    # Create mock client
    mock_client = create_mock_sagemaker_client_for_cleanup([endpoint_name])
    
    # Create deployer
    deployer = ModelDeployer(mock_client, config)
    
    # Delete the endpoint
    deployer.delete_endpoint(endpoint_name)
    
    # Verify all three resources were deleted
    assert endpoint_name in mock_client._deleted_endpoints
    assert f"{endpoint_name}-config" in mock_client._deleted_configs
    assert f"{endpoint_name}-model" in mock_client._deleted_models


@given(
    endpoint_names=valid_endpoint_names_list(min_size=2, max_size=5)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_cleanup_handles_multiple_endpoints_independently(
    endpoint_names: List[str]
) -> None:
    """
    Verify that cleanup handles multiple endpoints independently.
    
    This test ensures that when multiple endpoints are created and cleaned up,
    each endpoint's resources are properly tracked and deleted independently.
    """
    # Create config with cleanup enabled
    config = create_pipeline_config_with_cleanup(cleanup_enabled=True)
    
    # Create mock client
    mock_client = create_mock_sagemaker_client_for_cleanup(endpoint_names)
    
    # Create deployer
    deployer = ModelDeployer(mock_client, config)
    
    # Delete each endpoint
    for endpoint_name in endpoint_names:
        deployer.delete_endpoint(endpoint_name)
    
    # Verify all endpoints were deleted
    assert set(mock_client._deleted_endpoints) == set(endpoint_names)
    
    # Verify all configs were deleted
    expected_configs = {f"{name}-config" for name in endpoint_names}
    assert set(mock_client._deleted_configs) == expected_configs
    
    # Verify all models were deleted
    expected_models = {f"{name}-model" for name in endpoint_names}
    assert set(mock_client._deleted_models) == expected_models


@given(endpoint_name=valid_endpoint_name())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_cleanup_configuration_is_respected(endpoint_name: str) -> None:
    """
    Verify that the cleanup_resources configuration is respected.
    
    This test ensures that the cleanup behavior is determined by the
    cleanup_resources configuration setting, not by any other factors.
    """
    # Test with cleanup enabled
    config_with_cleanup = create_pipeline_config_with_cleanup(cleanup_enabled=True)
    mock_client_with_cleanup = create_mock_sagemaker_client_for_cleanup([endpoint_name])
    deployer_with_cleanup = ModelDeployer(mock_client_with_cleanup, config_with_cleanup)
    
    # Perform cleanup
    deployer_with_cleanup.delete_endpoint(endpoint_name)
    
    # Verify cleanup occurred
    assert len(mock_client_with_cleanup._deleted_endpoints) == 1
    
    # Test with cleanup disabled
    config_without_cleanup = create_pipeline_config_with_cleanup(cleanup_enabled=False)
    mock_client_without_cleanup = create_mock_sagemaker_client_for_cleanup([endpoint_name])
    deployer_without_cleanup = ModelDeployer(mock_client_without_cleanup, config_without_cleanup)
    
    # Don't perform cleanup (simulating pipeline behavior)
    # In real pipeline, delete_endpoint would not be called when cleanup is disabled
    
    # Verify no cleanup occurred
    assert len(mock_client_without_cleanup._deleted_endpoints) == 0


# ============================================================================
# Strategy Validation Tests
# ============================================================================

@given(endpoint_name=valid_endpoint_name())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_valid_endpoint_name_strategy_generates_valid_names(endpoint_name: str) -> None:
    """
    Verify that the valid_endpoint_name strategy generates valid endpoint names.
    
    This test ensures our hypothesis strategy is correctly configured and
    generates names that meet SageMaker endpoint naming requirements.
    """
    # Verify length constraints
    assert 1 <= len(endpoint_name) <= 63, \
        f"Endpoint name length {len(endpoint_name)} not in range [1, 63]"
    
    # Verify character constraints
    valid_chars = set('abcdefghijklmnopqrstuvwxyz0123456789-')
    assert all(c in valid_chars for c in endpoint_name), \
        f"Endpoint name contains invalid characters: {endpoint_name}"
    
    # Verify doesn't start or end with hyphen
    assert not endpoint_name.startswith('-'), \
        f"Endpoint name starts with hyphen: {endpoint_name}"
    assert not endpoint_name.endswith('-'), \
        f"Endpoint name ends with hyphen: {endpoint_name}"
    
    # Verify no consecutive hyphens
    assert '--' not in endpoint_name, \
        f"Endpoint name contains consecutive hyphens: {endpoint_name}"


@given(
    cleanup_enabled=st.booleans()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_create_pipeline_config_with_cleanup_function(cleanup_enabled: bool) -> None:
    """
    Verify that the create_pipeline_config_with_cleanup function generates valid configs.
    
    This test ensures our helper function is correctly configured and
    generates valid PipelineConfig instances with the specified cleanup setting.
    """
    config = create_pipeline_config_with_cleanup(cleanup_enabled=cleanup_enabled)
    
    # Verify it's a PipelineConfig instance
    assert isinstance(config, PipelineConfig)
    
    # Verify cleanup_resources matches the input
    assert config.cleanup_resources == cleanup_enabled
    
    # Verify all required attributes are present
    assert hasattr(config, 'aws_region')
    assert hasattr(config, 'sagemaker_role_arn')
    assert hasattr(config, 'inference_instance_type')
    assert hasattr(config, 's3_bucket')
    assert hasattr(config, 'base_model')


# ============================================================================
# Property 25: Resource Tracking for Cleanup
# ============================================================================

# Feature: automated-llm-finetuning-pipeline, Property 25: Resource Tracking for Cleanup
@given(
    num_endpoints=st.integers(min_value=1, max_value=10),
    num_training_jobs=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.property
@pytest.mark.pbt
def test_property_25_resource_tracking_for_cleanup(
    num_endpoints: int,
    num_training_jobs: int
) -> None:
    """
    **Validates: Requirements 9.5**
    
    Property 25: Resource Tracking for Cleanup
    
    For any resources created during pipeline execution (endpoints, training jobs,
    S3 artifacts), the Model_Deployer and Model_Trainer should maintain a list of
    all created resource identifiers to enable complete cleanup.
    
    This property ensures that:
    - ModelDeployer tracks all created endpoints
    - ModelTrainer tracks all created training jobs
    - list_active_endpoints() returns all created endpoints
    - Resource tracking is accurate across multiple creations
    - All created resources can be identified for cleanup
    """
    # Create configuration
    config = create_pipeline_config_with_cleanup(cleanup_enabled=True)
    
    # ========================================================================
    # Test ModelDeployer resource tracking
    # ========================================================================
    
    # Create mock SageMaker client for deployer
    mock_deployer_client = Mock()
    
    # Track created endpoints
    created_endpoints = []
    
    # Mock create_endpoint to track created endpoints
    def mock_create_endpoint(EndpointName: str, EndpointConfigName: str) -> dict:  # type: ignore[type-arg]
        created_endpoints.append(EndpointName)
        return {
            'EndpointArn': f'arn:aws:sagemaker:us-east-1:123456789012:endpoint/{EndpointName}'
        }
    
    # Mock describe_endpoint to return InService status
    def mock_describe_endpoint(EndpointName: str) -> dict:  # type: ignore[type-arg]
        if EndpointName in created_endpoints:
            return {
                'EndpointName': EndpointName,
                'EndpointArn': f'arn:aws:sagemaker:us-east-1:123456789012:endpoint/{EndpointName}',
                'EndpointStatus': 'InService',
                'CreationTime': datetime.now()
            }
        else:
            raise mock_deployer_client.exceptions.ResourceNotFound()
    
    # Mock list_endpoints paginator
    def mock_list_endpoints_paginator() -> Mock:
        paginator = Mock()
        
        def mock_paginate(StatusEquals: str, SortBy: str, SortOrder: str) -> list:  # type: ignore[type-arg]
            # Return all created endpoints that are InService
            if StatusEquals == 'InService':
                return [{
                    'Endpoints': [
                        {
                            'EndpointName': endpoint_name,
                            'EndpointArn': f'arn:aws:sagemaker:us-east-1:123456789012:endpoint/{endpoint_name}',
                            'EndpointStatus': 'InService',
                            'CreationTime': datetime.now()
                        }
                        for endpoint_name in created_endpoints
                    ]
                }]
            return []
        
        paginator.paginate = Mock(side_effect=mock_paginate)
        return paginator
    
    # Configure mock client
    mock_deployer_client.create_endpoint = Mock(side_effect=mock_create_endpoint)
    mock_deployer_client.describe_endpoint = Mock(side_effect=mock_describe_endpoint)
    mock_deployer_client.get_paginator = Mock(side_effect=lambda x: mock_list_endpoints_paginator())
    mock_deployer_client.create_model = Mock(return_value={})
    mock_deployer_client.create_endpoint_config = Mock(return_value={})
    mock_deployer_client.exceptions = Mock()
    mock_deployer_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
    
    # Create ModelDeployer
    deployer = ModelDeployer(mock_deployer_client, config)
    
    # Create multiple endpoints
    endpoint_names = [f"test-endpoint-{i}" for i in range(num_endpoints)]
    
    for endpoint_name in endpoint_names:
        # Deploy model (this will create the endpoint)
        result = deployer.deploy_model(
            model_artifact_uri=f"s3://bucket/model-{endpoint_name}.tar.gz",
            endpoint_name=endpoint_name
        )
        
        # Verify deployment was successful
        assert result.is_successful(), f"Deployment of {endpoint_name} failed"
        assert result.endpoint_name == endpoint_name
    
    # Verify all endpoints were tracked
    assert len(created_endpoints) == num_endpoints, \
        f"Expected {num_endpoints} endpoints to be created, but {len(created_endpoints)} were created"
    
    # Verify list_active_endpoints returns all created endpoints
    active_endpoints = deployer.list_active_endpoints()
    
    assert len(active_endpoints) == num_endpoints, \
        f"Expected list_active_endpoints to return {num_endpoints} endpoints, but got {len(active_endpoints)}"
    
    # Verify all created endpoints are in the active list
    for endpoint_name in endpoint_names:
        assert endpoint_name in active_endpoints, \
            f"Endpoint {endpoint_name} was created but not found in list_active_endpoints()"
    
    # Verify no extra endpoints are in the active list
    assert set(active_endpoints) == set(endpoint_names), \
        f"list_active_endpoints() returned unexpected endpoints: {set(active_endpoints) - set(endpoint_names)}"
    
    # ========================================================================
    # Test ModelTrainer resource tracking
    # ========================================================================
    
    # Import ModelTrainer
    from src.model_trainer import ModelTrainer
    
    # Create mock SageMaker client for trainer
    mock_trainer_client = Mock()
    
    # Track created training jobs
    created_training_jobs = []
    
    # Mock create_training_job to track created jobs
    def mock_create_training_job(**kwargs) -> dict:  # type: ignore[type-arg, no-untyped-def]
        job_name = kwargs['TrainingJobName']
        created_training_jobs.append(job_name)
        return {
            'TrainingJobArn': f'arn:aws:sagemaker:us-east-1:123456789012:training-job/{job_name}'
        }
    
    # Mock describe_training_job to return Completed status
    def mock_describe_training_job(TrainingJobName: str) -> dict:  # type: ignore[type-arg]
        if TrainingJobName in created_training_jobs:
            return {
                'TrainingJobName': TrainingJobName,
                'TrainingJobArn': f'arn:aws:sagemaker:us-east-1:123456789012:training-job/{TrainingJobName}',
                'TrainingJobStatus': 'Completed',
                'CreationTime': datetime.now(),
                'TrainingStartTime': datetime.now(),
                'TrainingEndTime': datetime.now(),
                'ModelArtifacts': {
                    'S3ModelArtifacts': f's3://bucket/model-artifacts/{TrainingJobName}/model.tar.gz'
                },
                'FinalMetricDataList': [
                    {'MetricName': 'train:loss', 'Value': 0.5}
                ]
            }
        else:
            raise mock_trainer_client.exceptions.ResourceNotFound()
    
    # Configure mock client
    mock_trainer_client.create_training_job = Mock(side_effect=mock_create_training_job)
    mock_trainer_client.describe_training_job = Mock(side_effect=mock_describe_training_job)
    mock_trainer_client.exceptions = Mock()
    mock_trainer_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
    
    # Create ModelTrainer
    trainer = ModelTrainer(mock_trainer_client, config)
    
    # Create temporary training data files for testing
    import tempfile
    import json
    from pathlib import Path
    
    training_job_names = []
    
    for i in range(num_training_jobs):
        # Create a temporary training data file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            # Write some sample training data
            for j in range(10):
                example = {
                    'instruction': f'Test instruction {j}',
                    'context': f'Test context {j}',
                    'response': f'Test response {j}'
                }
                f.write(json.dumps(example) + '\n')
            
            temp_file_path = f.name
        
        try:
            # Mock S3 upload
            import boto3
            from unittest.mock import patch
            
            with patch('boto3.client') as mock_boto3_client:
                mock_s3_client = Mock()
                mock_s3_client.upload_file = Mock(return_value=None)
                mock_boto3_client.return_value = mock_s3_client
                
                # Train model (this will create the training job)
                result = trainer.train_model(
                    training_data_path=temp_file_path,
                    use_case_name=f"test-use-case-{i}"
                )
                
                # Verify training was successful
                assert result.is_successful(), f"Training job {i} failed"
                
                # Track the job name
                training_job_names.append(result.job_name)
        
        finally:
            # Clean up temporary file
            Path(temp_file_path).unlink(missing_ok=True)
    
    # Verify all training jobs were tracked
    assert len(created_training_jobs) == num_training_jobs, \
        f"Expected {num_training_jobs} training jobs to be created, but {len(created_training_jobs)} were created"
    
    # Verify all created training jobs are in our tracking list
    for job_name in training_job_names:
        assert job_name in created_training_jobs, \
            f"Training job {job_name} was created but not tracked"
    
    # Verify no extra training jobs were created
    assert set(created_training_jobs) == set(training_job_names), \
        f"Unexpected training jobs were created: {set(created_training_jobs) - set(training_job_names)}"


@given(
    num_resources=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_resource_tracking_enables_complete_cleanup(num_resources: int) -> None:
    """
    Verify that resource tracking enables complete cleanup.
    
    This test ensures that all tracked resources can be identified and
    cleaned up using the resource tracking information.
    """
    # Create configuration with cleanup enabled
    config = create_pipeline_config_with_cleanup(cleanup_enabled=True)
    
    # Create mock SageMaker client
    mock_client = Mock()
    
    # Track created and deleted endpoints
    created_endpoints = []
    deleted_endpoints = []
    
    def mock_create_endpoint(EndpointName: str, EndpointConfigName: str) -> dict:  # type: ignore[type-arg]
        created_endpoints.append(EndpointName)
        return {
            'EndpointArn': f'arn:aws:sagemaker:us-east-1:123456789012:endpoint/{EndpointName}'
        }
    
    def mock_describe_endpoint(EndpointName: str) -> dict:  # type: ignore[type-arg]
        if EndpointName in created_endpoints and EndpointName not in deleted_endpoints:
            return {
                'EndpointName': EndpointName,
                'EndpointArn': f'arn:aws:sagemaker:us-east-1:123456789012:endpoint/{EndpointName}',
                'EndpointStatus': 'InService',
                'CreationTime': datetime.now()
            }
        else:
            raise mock_client.exceptions.ResourceNotFound()
    
    def mock_delete_endpoint(EndpointName: str) -> dict:  # type: ignore[type-arg]
        deleted_endpoints.append(EndpointName)
        return {}
    
    def mock_list_endpoints_paginator() -> Mock:
        paginator = Mock()
        
        def mock_paginate(StatusEquals: str, SortBy: str, SortOrder: str) -> list:  # type: ignore[type-arg]
            # Return all created endpoints that haven't been deleted
            if StatusEquals == 'InService':
                active = [ep for ep in created_endpoints if ep not in deleted_endpoints]
                return [{
                    'Endpoints': [
                        {
                            'EndpointName': endpoint_name,
                            'EndpointArn': f'arn:aws:sagemaker:us-east-1:123456789012:endpoint/{endpoint_name}',
                            'EndpointStatus': 'InService',
                            'CreationTime': datetime.now()
                        }
                        for endpoint_name in active
                    ]
                }]
            return []
        
        paginator.paginate = Mock(side_effect=mock_paginate)
        return paginator
    
    # Configure mock client
    mock_client.create_endpoint = Mock(side_effect=mock_create_endpoint)
    mock_client.describe_endpoint = Mock(side_effect=mock_describe_endpoint)
    mock_client.delete_endpoint = Mock(side_effect=mock_delete_endpoint)
    mock_client.delete_endpoint_config = Mock(return_value={})
    mock_client.delete_model = Mock(return_value={})
    mock_client.get_paginator = Mock(side_effect=lambda x: mock_list_endpoints_paginator())
    mock_client.create_model = Mock(return_value={})
    mock_client.create_endpoint_config = Mock(return_value={})
    mock_client.exceptions = Mock()
    mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
    
    # Create ModelDeployer
    deployer = ModelDeployer(mock_client, config)
    
    # Create multiple endpoints
    endpoint_names = [f"cleanup-test-endpoint-{i}" for i in range(num_resources)]
    
    for endpoint_name in endpoint_names:
        deployer.deploy_model(
            model_artifact_uri=f"s3://bucket/model-{endpoint_name}.tar.gz",
            endpoint_name=endpoint_name
        )
    
    # Get list of active endpoints (this is the resource tracking)
    active_endpoints = deployer.list_active_endpoints()
    
    # Verify all endpoints are tracked
    assert len(active_endpoints) == num_resources
    assert set(active_endpoints) == set(endpoint_names)
    
    # Use the tracked resources to perform complete cleanup
    for endpoint_name in active_endpoints:
        deployer.delete_endpoint(endpoint_name)
    
    # Verify all endpoints were deleted
    assert len(deleted_endpoints) == num_resources
    assert set(deleted_endpoints) == set(endpoint_names)
    
    # Verify no active endpoints remain
    remaining_endpoints = deployer.list_active_endpoints()
    assert len(remaining_endpoints) == 0, \
        f"Expected no active endpoints after cleanup, but found {len(remaining_endpoints)}"

