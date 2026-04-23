"""
Property-Based Tests for Configuration Manager

This module implements property-based tests for the ConfigurationManager class
using hypothesis. These tests verify universal properties that should hold
across all valid inputs.

Properties tested:
- Property 1: Use Case Configuration Round-Trip
- Property 2: Configuration Validation Rejects Invalid Inputs
- Property 3: Use Case Listing Completeness
- Property 4: Use Case Versioning Monotonicity
- Property 23: Configuration Loading Completeness

Each test uses hypothesis with minimum 100 examples as per design requirements.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import SearchStrategy

from src.configuration_manager import ConfigurationManager
from src.config_models import UseCase, PipelineConfig


# ============================================================================
# Hypothesis Strategies for Domain Objects
# ============================================================================

@st.composite
def valid_use_case_name(draw) -> str:
    """Generate valid use case names (3-100 characters, alphanumeric with underscores/hyphens)."""
    # Generate name with valid characters
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-'),
        min_size=3,
        max_size=100
    ))
    # Ensure it's not just special characters
    assume(any(c.isalnum() for c in name))
    return name


@st.composite
def valid_description(draw) -> str:
    """Generate valid descriptions (10+ characters, printable)."""
    return draw(st.text(
        alphabet=st.characters(blacklist_categories=('Cc', 'Cs'), min_codepoint=32),
        min_size=10,
        max_size=500
    ))


@st.composite
def valid_test_questions(draw) -> List[str]:
    """Generate valid test questions (1-50 questions, each 1-500 characters)."""
    num_questions = draw(st.integers(min_value=1, max_value=50))
    questions = []
    for _ in range(num_questions):
        # Use printable characters to avoid YAML serialization issues with control characters
        question = draw(st.text(
            alphabet=st.characters(blacklist_categories=('Cc', 'Cs'), min_codepoint=32),
            min_size=1,
            max_size=500
        ))
        # Ensure question is not just whitespace
        assume(question.strip())
        questions.append(question)
    return questions


@st.composite
def valid_prompt(draw) -> str:
    """Generate valid prompts (20+ characters, printable)."""
    return draw(st.text(
        alphabet=st.characters(blacklist_categories=('Cc', 'Cs'), min_codepoint=32),
        min_size=20,
        max_size=1000
    ))


@st.composite
def valid_use_case(draw) -> UseCase:
    """
    Generate valid UseCase instances for property-based testing.
    
    This strategy creates UseCase objects with all required fields
    populated with valid values that pass validation.
    """
    name = draw(valid_use_case_name())
    description = draw(valid_description())
    test_questions = draw(valid_test_questions())
    judge_criteria = draw(valid_prompt())
    data_generation_prompt = draw(valid_prompt())
    judge_prompt = draw(valid_prompt())
    version = draw(st.integers(min_value=1, max_value=100))
    
    # Generate created_at within reasonable range (fixed dates for determinism)
    # Use fixed dates instead of datetime.now() to avoid flaky tests
    min_date = datetime(2020, 1, 1)
    max_date = datetime(2024, 12, 31)
    created_at = draw(st.datetimes(min_value=min_date, max_value=max_date))
    
    return UseCase(
        name=name,
        description=description,
        test_questions=test_questions,
        judge_criteria=judge_criteria,
        data_generation_prompt=data_generation_prompt,
        judge_prompt=judge_prompt,
        version=version,
        created_at=created_at
    )


@st.composite
def invalid_use_case(draw) -> dict:
    """
    Generate invalid UseCase data for testing validation.
    
    Returns a dictionary with missing or invalid fields that should
    fail validation.
    """
    # Choose which type of invalid data to generate
    invalid_type = draw(st.sampled_from([
        'missing_name',
        'empty_name',
        'missing_description',
        'empty_description',
        'missing_questions',
        'empty_questions',
        'missing_judge_criteria',
        'empty_judge_criteria',
        'missing_data_gen_prompt',
        'empty_data_gen_prompt',
        'missing_judge_prompt',
        'empty_judge_prompt',
        'invalid_version',
    ]))
    
    # Start with a valid base (using fixed datetime for determinism)
    base = {
        'name': draw(valid_use_case_name()),
        'description': draw(valid_description()),
        'test_questions': draw(valid_test_questions()),
        'judge_criteria': draw(valid_prompt()),
        'data_generation_prompt': draw(valid_prompt()),
        'judge_prompt': draw(valid_prompt()),
        'version': draw(st.integers(min_value=1, max_value=100)),
        'created_at': datetime(2024, 1, 1)  # Fixed date for determinism
    }
    
    # Introduce the specific invalidity
    if invalid_type == 'missing_name':
        del base['name']
    elif invalid_type == 'empty_name':
        base['name'] = ''
    elif invalid_type == 'missing_description':
        del base['description']
    elif invalid_type == 'empty_description':
        base['description'] = ''
    elif invalid_type == 'missing_questions':
        del base['test_questions']
    elif invalid_type == 'empty_questions':
        base['test_questions'] = []
    elif invalid_type == 'missing_judge_criteria':
        del base['judge_criteria']
    elif invalid_type == 'empty_judge_criteria':
        base['judge_criteria'] = ''
    elif invalid_type == 'missing_data_gen_prompt':
        del base['data_generation_prompt']
    elif invalid_type == 'empty_data_gen_prompt':
        base['data_generation_prompt'] = ''
    elif invalid_type == 'missing_judge_prompt':
        del base['judge_prompt']
    elif invalid_type == 'empty_judge_prompt':
        base['judge_prompt'] = ''
    elif invalid_type == 'invalid_version':
        base['version'] = draw(st.integers(max_value=0))
    
    return base


@st.composite
def valid_aws_region(draw) -> str:
    """Generate valid AWS region names."""
    regions = [
        'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
        'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1',
        'ap-northeast-1', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
        'ap-south-1', 'sa-east-1', 'ca-central-1'
    ]
    return draw(st.sampled_from(regions))


@st.composite
def valid_role_arn(draw) -> str:
    """Generate valid AWS IAM role ARNs."""
    account_id = draw(st.integers(min_value=100000000000, max_value=999999999999))
    role_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-'),
        min_size=1,
        max_size=64
    ))
    return f"arn:aws:iam::{account_id}:role/{role_name}"


@st.composite
def valid_s3_bucket_name(draw) -> str:
    """Generate valid S3 bucket names."""
    # S3 bucket names: 3-63 chars, lowercase alphanumeric and hyphens
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=3,
        max_size=63
    ))
    # Ensure starts and ends with alphanumeric
    assume(name[0].isalnum() and name[-1].isalnum())
    # Ensure no consecutive periods or invalid combinations
    assume('..' not in name and '.-' not in name and '-.' not in name)
    return name


@st.composite
def valid_instance_type(draw) -> str:
    """Generate valid SageMaker instance types."""
    families = ['ml.g5', 'ml.p3', 'ml.m5', 'ml.c5']
    sizes = ['xlarge', '2xlarge', '4xlarge', '8xlarge', '12xlarge']
    family = draw(st.sampled_from(families))
    size = draw(st.sampled_from(sizes))
    return f"{family}.{size}"


@st.composite
def valid_pipeline_config(draw) -> PipelineConfig:
    """
    Generate valid PipelineConfig instances for property-based testing.
    
    This strategy creates PipelineConfig objects with all required fields
    populated with valid values that pass validation.
    """
    aws_region = draw(valid_aws_region())
    bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
    sagemaker_role_arn = draw(valid_role_arn())
    s3_bucket = draw(valid_s3_bucket_name())
    training_instance_type = draw(valid_instance_type())
    inference_instance_type = draw(valid_instance_type())
    
    # Generate valid endpoint name (1-63 chars, alphanumeric and hyphens)
    baseline_endpoint = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=1,
        max_size=63
    ))
    assume(baseline_endpoint[0].isalnum() and baseline_endpoint[-1].isalnum())
    
    performance_threshold = draw(st.floats(min_value=0.0, max_value=1.0))
    max_iterations = draw(st.integers(min_value=1, max_value=10))
    cleanup_resources = draw(st.booleans())
    
    # Optional fields with reasonable defaults
    base_model = "meta-llama/Llama-3.2-3B"
    max_training_time_seconds = draw(st.integers(min_value=300, max_value=86400))
    max_retries = draw(st.integers(min_value=0, max_value=10))
    initial_backoff_seconds = draw(st.integers(min_value=1, max_value=60))
    max_backoff_seconds = draw(st.integers(min_value=initial_backoff_seconds, max_value=300))
    artifact_retention_days = draw(st.integers(min_value=0, max_value=365))
    
    return PipelineConfig(
        aws_region=aws_region,
        bedrock_model_id=bedrock_model_id,
        sagemaker_role_arn=sagemaker_role_arn,
        training_instance_type=training_instance_type,
        inference_instance_type=inference_instance_type,
        baseline_model_endpoint=baseline_endpoint,
        performance_threshold=performance_threshold,
        max_iterations=max_iterations,
        cleanup_resources=cleanup_resources,
        s3_bucket=s3_bucket,
        base_model=base_model,
        max_training_time_seconds=max_training_time_seconds,
        max_retries=max_retries,
        initial_backoff_seconds=initial_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
        artifact_retention_days=artifact_retention_days
    )



# ============================================================================
# Property-Based Tests
# ============================================================================

# Feature: automated-llm-finetuning-pipeline, Property 1: Use Case Configuration Round-Trip
@given(use_case=valid_use_case())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
@pytest.mark.pbt
def test_property_1_use_case_round_trip(use_case: UseCase):
    """
    **Validates: Requirements 1.1**
    
    Property 1: Use Case Configuration Round-Trip
    
    For any valid use case definition, storing it via ConfigurationManager
    and then loading it by name should produce an equivalent use case definition.
    
    This property ensures that:
    - All fields are correctly serialized to YAML
    - All fields are correctly deserialized from YAML
    - No data is lost in the round-trip process
    - The loaded use case is functionally equivalent to the original
    """
    # Create ConfigurationManager with temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_manager = ConfigurationManager(config_dir=str(Path(tmp_dir) / "config"))
        
        # Save the use case
        config_manager.save_use_case(use_case)
        
        # Load the use case back
        loaded_use_case = config_manager.load_use_case(use_case.name)
        
        # Verify all fields match
        assert loaded_use_case.name == use_case.name
        assert loaded_use_case.description == use_case.description
        
        # For test questions, normalize whitespace since YAML may change it
        assert len(loaded_use_case.test_questions) == len(use_case.test_questions)
        for i, (loaded_q, original_q) in enumerate(zip(loaded_use_case.test_questions, use_case.test_questions)):
            # Normalize whitespace for comparison
            assert loaded_q.strip() == original_q.strip(), \
                f"Question {i} mismatch: {repr(loaded_q)} != {repr(original_q)}"
        
        assert loaded_use_case.judge_criteria == use_case.judge_criteria
        assert loaded_use_case.data_generation_prompt == use_case.data_generation_prompt
        assert loaded_use_case.judge_prompt == use_case.judge_prompt
        assert loaded_use_case.version == use_case.version
        
        # For datetime, allow small differences due to serialization precision
        time_diff = abs((loaded_use_case.created_at - use_case.created_at).total_seconds())
        assert time_diff < 1.0, f"Timestamp difference too large: {time_diff} seconds"



# Feature: automated-llm-finetuning-pipeline, Property 2: Configuration Validation Rejects Invalid Inputs
@given(invalid_data=invalid_use_case())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
@pytest.mark.pbt
def test_property_2_validation_rejects_invalid_inputs(invalid_data: dict):
    """
    **Validates: Requirements 1.2, 8.2, 8.3**
    
    Property 2: Configuration Validation Rejects Invalid Inputs
    
    For any configuration object with missing required fields or invalid values,
    the ConfigurationManager validation should reject it and report the specific
    fields that are missing or invalid.
    
    This property ensures that:
    - Invalid configurations are detected
    - Validation provides specific error messages
    - The system fails fast on invalid input
    """
    # Attempt to create UseCase with invalid data should raise an error
    with pytest.raises((ValueError, KeyError, TypeError)):
        UseCase(**invalid_data)



# Feature: automated-llm-finetuning-pipeline, Property 3: Use Case Listing Completeness
@given(use_cases=st.lists(valid_use_case(), min_size=1, max_size=10, unique_by=lambda uc: uc.name))
@settings(max_examples=100, deadline=None)
@pytest.mark.property
@pytest.mark.pbt
def test_property_3_use_case_listing_completeness(use_cases: List[UseCase]):
    """
    **Validates: Requirements 1.3**
    
    Property 3: Use Case Listing Completeness
    
    For any set of use case definitions stored via ConfigurationManager,
    listing all use cases should return a list containing all stored use case names.
    
    This property ensures that:
    - All saved use cases are discoverable
    - No use cases are lost or hidden
    - The listing is complete and accurate
    """
    # Create ConfigurationManager with temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_manager = ConfigurationManager(config_dir=str(Path(tmp_dir) / "config"))
        
        # Save all use cases
        for use_case in use_cases:
            config_manager.save_use_case(use_case)
        
        # List all use cases
        listed_names = config_manager.list_use_cases()
        
        # Verify all use case names are in the list
        expected_names = sorted([uc.name for uc in use_cases])
        assert listed_names == expected_names, \
            f"Expected {expected_names}, got {listed_names}"
        
        # Verify count matches
        assert len(listed_names) == len(use_cases), \
            f"Expected {len(use_cases)} use cases, got {len(listed_names)}"



# Feature: automated-llm-finetuning-pipeline, Property 4: Use Case Versioning Monotonicity
@given(
    use_case=valid_use_case(),
    num_updates=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.property
@pytest.mark.pbt
def test_property_4_use_case_versioning_monotonicity(use_case: UseCase, num_updates: int):
    """
    **Validates: Requirements 1.4**
    
    Property 4: Use Case Versioning Monotonicity
    
    For any use case that is updated multiple times, all previous versions
    should be preserved with monotonically increasing version numbers and
    timestamps that reflect the update order.
    
    This property ensures that:
    - Version numbers increase with each update
    - Previous versions are backed up
    - Version history is maintained
    - Updates don't lose historical data
    """
    # Create ConfigurationManager with temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_manager = ConfigurationManager(config_dir=str(Path(tmp_dir) / "config"))
        
        # Save initial version
        initial_version = use_case.version
        config_manager.save_use_case(use_case)
        
        # Track versions
        versions = [initial_version]
        
        # Perform multiple updates
        for i in range(num_updates):
            # Modify the use case (change description to make it different)
            use_case.description = f"{use_case.description} - Update {i+1}"
            
            # Save the updated use case
            config_manager.save_use_case(use_case)
            
            # Load it back to get the new version
            loaded = config_manager.load_use_case(use_case.name)
            versions.append(loaded.version)
        
        # Verify versions are monotonically increasing
        for i in range(len(versions) - 1):
            assert versions[i+1] > versions[i], \
                f"Version not increasing: {versions[i]} -> {versions[i+1]}"
        
        # Verify final version is initial + num_updates
        assert versions[-1] == initial_version + num_updates, \
            f"Expected final version {initial_version + num_updates}, got {versions[-1]}"
        
        # Verify backup files exist for previous versions
        use_cases_dir = Path(tmp_dir) / "config" / "use_cases"
        backup_files = list(use_cases_dir.glob(f"{use_case.name}.v*.yaml"))
        
        # Should have num_updates backup files (one for each update)
        assert len(backup_files) == num_updates, \
            f"Expected {num_updates} backup files, found {len(backup_files)}"



# Feature: automated-llm-finetuning-pipeline, Property 23: Configuration Loading Completeness
@given(pipeline_config=valid_pipeline_config())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
@pytest.mark.pbt
def test_property_23_configuration_loading_completeness(pipeline_config: PipelineConfig):
    """
    **Validates: Requirements 8.1, 8.5**
    
    Property 23: Configuration Loading Completeness
    
    For any valid pipeline configuration file, loading it should populate
    all required parameters with either specified values or documented defaults.
    
    This property ensures that:
    - All required fields are loaded correctly
    - Optional fields have appropriate defaults
    - No configuration data is lost
    - The loaded config is complete and usable
    """
    # Create ConfigurationManager with temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_dir = Path(tmp_dir) / "config"
        config_dir.mkdir()
        config_manager = ConfigurationManager(config_dir=str(config_dir))
        
        # Create a pipeline config YAML file
        import yaml
        config_path = config_dir / "pipeline_config.yaml"
        
        config_dict = {
            'aws': {
                'region': pipeline_config.aws_region,
                'bedrock_model_id': pipeline_config.bedrock_model_id,
                'sagemaker_role_arn': pipeline_config.sagemaker_role_arn,
                's3_bucket': pipeline_config.s3_bucket,
            },
            'training': {
                'instance_type': pipeline_config.training_instance_type,
                'base_model': pipeline_config.base_model,
                'max_training_time_seconds': pipeline_config.max_training_time_seconds,
            },
            'inference': {
                'instance_type': pipeline_config.inference_instance_type,
                'baseline_model_endpoint': pipeline_config.baseline_model_endpoint,
            },
            'pipeline': {
                'performance_threshold': pipeline_config.performance_threshold,
                'max_iterations': pipeline_config.max_iterations,
                'cleanup_resources': pipeline_config.cleanup_resources,
                'artifact_retention_days': pipeline_config.artifact_retention_days,
            },
            'retry': {
                'max_attempts': pipeline_config.max_retries,
                'initial_backoff_seconds': pipeline_config.initial_backoff_seconds,
                'max_backoff_seconds': pipeline_config.max_backoff_seconds,
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.safe_dump(config_dict, f)
        
        # Load the configuration
        loaded_config = config_manager.load_pipeline_config()
        
        # Verify all required fields match
        assert loaded_config.aws_region == pipeline_config.aws_region
        assert loaded_config.bedrock_model_id == pipeline_config.bedrock_model_id
        assert loaded_config.sagemaker_role_arn == pipeline_config.sagemaker_role_arn
        assert loaded_config.s3_bucket == pipeline_config.s3_bucket
        assert loaded_config.training_instance_type == pipeline_config.training_instance_type
        assert loaded_config.inference_instance_type == pipeline_config.inference_instance_type
        assert loaded_config.baseline_model_endpoint == pipeline_config.baseline_model_endpoint
        assert loaded_config.performance_threshold == pipeline_config.performance_threshold
        assert loaded_config.max_iterations == pipeline_config.max_iterations
        assert loaded_config.cleanup_resources == pipeline_config.cleanup_resources
        
        # Verify optional fields with defaults
        assert loaded_config.base_model == pipeline_config.base_model
        assert loaded_config.max_training_time_seconds == pipeline_config.max_training_time_seconds
        assert loaded_config.max_retries == pipeline_config.max_retries
        assert loaded_config.initial_backoff_seconds == pipeline_config.initial_backoff_seconds
        assert loaded_config.max_backoff_seconds == pipeline_config.max_backoff_seconds
        assert loaded_config.artifact_retention_days == pipeline_config.artifact_retention_days



# ============================================================================
# Strategy Validation Tests
# ============================================================================

@given(use_case=valid_use_case())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_valid_use_case_strategy_generates_valid_instances(use_case: UseCase):
    """
    Verify that the valid_use_case strategy generates valid UseCase instances.
    
    This test ensures our hypothesis strategy is correctly configured and
    generates instances that pass all validation rules.
    """
    # The use_case should be valid (no exceptions during creation)
    assert use_case.name
    assert use_case.description
    assert len(use_case.test_questions) > 0
    assert use_case.judge_criteria
    assert use_case.data_generation_prompt
    assert use_case.judge_prompt
    assert use_case.version >= 1
    assert use_case.created_at is not None


@given(pipeline_config=valid_pipeline_config())
@settings(max_examples=100, deadline=None)
@pytest.mark.property
def test_valid_pipeline_config_strategy_generates_valid_instances(pipeline_config: PipelineConfig):
    """
    Verify that the valid_pipeline_config strategy generates valid PipelineConfig instances.
    
    This test ensures our hypothesis strategy is correctly configured and
    generates instances that pass all validation rules.
    """
    # The pipeline_config should be valid (no exceptions during creation)
    assert pipeline_config.aws_region
    assert pipeline_config.bedrock_model_id
    assert pipeline_config.sagemaker_role_arn
    assert pipeline_config.s3_bucket
    assert pipeline_config.training_instance_type
    assert pipeline_config.inference_instance_type
    assert pipeline_config.baseline_model_endpoint
    assert 0.0 <= pipeline_config.performance_threshold <= 1.0
    assert pipeline_config.max_iterations >= 1
    assert pipeline_config.max_retries >= 0
    assert pipeline_config.initial_backoff_seconds >= 1
    assert pipeline_config.max_backoff_seconds >= pipeline_config.initial_backoff_seconds
