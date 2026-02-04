"""
Pytest configuration and fixtures for the automated LLM finetuning pipeline tests.

This file contains:
- Hypothesis profile registration
- Common test fixtures
- Test utilities and helpers
"""
import pytest
from hypothesis import settings, Verbosity


# ============================================================================
# Hypothesis Profile Registration
# ============================================================================
# Register hypothesis profiles for different testing scenarios
# These profiles control how many examples are generated for property-based tests

# Default profile: Standard testing with 100 examples (as per design requirements)
settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
    derandomize=False,
    print_blob=True,
)

# CI profile: More thorough testing for continuous integration
settings.register_profile(
    "ci",
    max_examples=500,
    deadline=None,
    derandomize=False,
    print_blob=True,
)

# Debug profile: Fewer examples with verbose output for debugging failures
settings.register_profile(
    "debug",
    max_examples=10,
    verbosity=Verbosity.verbose,
    deadline=None,
    derandomize=True,
    print_blob=True,
)

# Quick profile: Fast iteration during development
settings.register_profile(
    "quick",
    max_examples=20,
    deadline=None,
    derandomize=False,
    print_blob=False,
)

# Load the default profile
settings.load_profile("default")


# ============================================================================
# Common Test Fixtures
# ============================================================================

@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary configuration directory for tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "use_cases").mkdir()
    return config_dir


@pytest.fixture
def temp_event_files_dir(tmp_path):
    """Create a temporary event_files directory for tests."""
    event_files_dir = tmp_path / "event_files"
    event_files_dir.mkdir()
    (event_files_dir / "questions").mkdir()
    (event_files_dir / "usecases").mkdir()
    (event_files_dir / "judge_prompts").mkdir()
    (event_files_dir / "training_data").mkdir()
    return event_files_dir


@pytest.fixture
def temp_progress_dir(tmp_path):
    """Create a temporary progress directory for tests."""
    progress_dir = tmp_path / "progress"
    progress_dir.mkdir()
    return progress_dir


@pytest.fixture
def temp_logs_dir(tmp_path):
    """Create a temporary logs directory for tests."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    return logs_dir


# ============================================================================
# AWS Mocking Fixtures (using moto)
# ============================================================================

@pytest.fixture
def aws_credentials():
    """
    Provide mock AWS credentials for moto.
    
    These credentials are used by boto3 when moto is active.
    They don't need to be real credentials.
    """
    import os
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    yield
    # Cleanup
    del os.environ["AWS_ACCESS_KEY_ID"]
    del os.environ["AWS_SECRET_ACCESS_KEY"]
    del os.environ["AWS_SECURITY_TOKEN"]
    del os.environ["AWS_SESSION_TOKEN"]
    del os.environ["AWS_DEFAULT_REGION"]


@pytest.fixture
def mock_sagemaker(aws_credentials):
    """
    Create a mocked SageMaker service using moto.
    
    This fixture provides a fully mocked SageMaker environment for testing
    training jobs, endpoints, and models without making real AWS API calls.
    
    Usage:
        def test_something(mock_sagemaker):
            # SageMaker is now mocked
            client = boto3.client('sagemaker', region_name='us-east-1')
            # Use client normally - all calls are mocked
    """
    from moto import mock_aws
    
    with mock_aws():
        yield


@pytest.fixture
def mock_s3(aws_credentials):
    """
    Create a mocked S3 service using moto.
    
    This fixture provides a fully mocked S3 environment for testing
    bucket operations, object uploads/downloads, and more.
    
    Usage:
        def test_something(mock_s3):
            # S3 is now mocked
            client = boto3.client('s3', region_name='us-east-1')
            # Create bucket and use normally
            client.create_bucket(Bucket='test-bucket')
    """
    from moto import mock_aws
    
    with mock_aws():
        yield


@pytest.fixture
def mock_bedrock(aws_credentials):
    """
    Create a mocked Bedrock Runtime service using moto.
    
    Note: Moto's Bedrock support may be limited. For complex Bedrock testing,
    consider using manual mocks or the AWSClientManager's mock_clients parameter.
    
    Usage:
        def test_something(mock_bedrock):
            # Bedrock Runtime is now mocked
            client = boto3.client('bedrock-runtime', region_name='us-east-1')
            # Use client - responses will be mocked
    """
    from moto import mock_aws
    
    with mock_aws():
        yield


@pytest.fixture
def mock_aws_services(aws_credentials):
    """
    Create mocked AWS services for SageMaker, S3, and Bedrock.
    
    This is a convenience fixture that mocks all AWS services at once.
    Use this when your test needs multiple AWS services.
    
    Usage:
        def test_something(mock_aws_services):
            # All AWS services are now mocked
            sagemaker = boto3.client('sagemaker', region_name='us-east-1')
            s3 = boto3.client('s3', region_name='us-east-1')
            bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    """
    from moto import mock_aws
    
    with mock_aws():
        yield


@pytest.fixture
def mock_sagemaker_with_role(mock_sagemaker):
    """
    Create a mocked SageMaker service with a pre-configured IAM role.
    
    This fixture extends mock_sagemaker by creating a mock IAM role
    that can be used for SageMaker training jobs and endpoints.
    
    Returns:
        str: ARN of the mocked IAM role
        
    Usage:
        def test_training_job(mock_sagemaker_with_role):
            role_arn = mock_sagemaker_with_role
            # Use role_arn in SageMaker API calls
    """
    import boto3
    
    # Create IAM client and role
    iam = boto3.client('iam', region_name='us-east-1')
    
    role_name = 'test-sagemaker-role'
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    import json
    response = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(assume_role_policy),
        Description='Mock SageMaker execution role for testing'
    )
    
    return response['Role']['Arn']


@pytest.fixture
def mock_s3_with_bucket(mock_s3):
    """
    Create a mocked S3 service with a pre-configured bucket.
    
    This fixture extends mock_s3 by creating a test bucket
    that can be used immediately in tests.
    
    Returns:
        str: Name of the created bucket
        
    Usage:
        def test_s3_upload(mock_s3_with_bucket):
            bucket_name = mock_s3_with_bucket
            # Upload files to bucket_name
    """
    import boto3
    
    bucket_name = 'test-finetuning-bucket'
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket=bucket_name)
    
    return bucket_name


@pytest.fixture
def aws_client_manager_with_mocks(mock_aws_services):
    """
    Create an AWSClientManager configured to use moto-mocked services.
    
    This fixture provides a fully configured AWSClientManager that uses
    moto for all AWS service calls. This is the recommended way to test
    components that use AWSClientManager.
    
    Returns:
        AWSClientManager: Configured manager with mocked AWS services
        
    Usage:
        def test_component(aws_client_manager_with_mocks):
            manager = aws_client_manager_with_mocks
            sagemaker = manager.get_sagemaker_client()
            # All SageMaker calls are mocked
    """
    from src.aws_client_manager import AWSClientManager
    
    config = {
        'region': 'us-east-1',
        'retry': {
            'max_attempts': 3,
            'initial_backoff_seconds': 0.1,  # Faster for tests
            'max_backoff_seconds': 1.0,
        }
    }
    
    return AWSClientManager(config)


# ============================================================================
# Test Markers and Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers documentation
    config.addinivalue_line(
        "markers",
        "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers",
        "property: Property-based tests using hypothesis"
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests requiring AWS services"
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests that take significant time to run"
    )
    config.addinivalue_line(
        "markers",
        "aws: Tests that interact with real AWS services"
    )
    config.addinivalue_line(
        "markers",
        "ui: Tests for Streamlit UI components"
    )
    config.addinivalue_line(
        "markers",
        "pbt: Property-based tests (alias for property marker)"
    )
    config.addinivalue_line(
        "markers",
        "aws_integration: Integration tests with real AWS services (requires credentials)"
    )
    config.addinivalue_line(
        "markers",
        "aws_mock: Tests using moto-mocked AWS services"
    )
    config.addinivalue_line(
        "markers",
        "requires_sagemaker: Tests requiring SageMaker service"
    )
    config.addinivalue_line(
        "markers",
        "requires_bedrock: Tests requiring Bedrock service"
    )
    config.addinivalue_line(
        "markers",
        "requires_s3: Tests requiring S3 service"
    )


# ============================================================================
# Test Collection Hooks
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark tests with hypothesis as property tests
        if "hypothesis" in item.keywords:
            item.add_marker(pytest.mark.property)
            item.add_marker(pytest.mark.pbt)
        
        # Auto-mark slow tests (tests that take > 5 seconds)
        # This can be refined based on actual test execution times
        if "slow" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
        
        # Auto-mark AWS integration tests
        if "aws_integration" in item.keywords or "aws" in item.keywords:
            # Skip AWS integration tests by default unless explicitly requested
            skip_aws = config.getoption("--skip-aws-integration", default=True)
            if skip_aws and "aws_integration" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(
                        reason="AWS integration tests skipped (use --run-aws-integration to enable)"
                    )
                )


def pytest_addoption(parser):
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--run-aws-integration",
        action="store_true",
        default=False,
        help="Run AWS integration tests that require real AWS credentials"
    )
    parser.addoption(
        "--skip-aws-integration",
        action="store_true",
        default=True,
        help="Skip AWS integration tests (default behavior)"
    )
    parser.addoption(
        "--aws-region",
        action="store",
        default="us-east-1",
        help="AWS region to use for integration tests (default: us-east-1)"
    )
    parser.addoption(
        "--aws-profile",
        action="store",
        default=None,
        help="AWS profile to use for integration tests (default: None, uses default credentials)"
    )


# ============================================================================
# AWS Integration Test Configuration
# ============================================================================

@pytest.fixture
def aws_integration_config(request):
    """
    Provide configuration for AWS integration tests.
    
    This fixture reads command-line options and provides configuration
    for tests that interact with real AWS services.
    
    Returns:
        dict: Configuration with keys:
            - region: AWS region to use
            - profile: AWS profile name (or None)
            - enabled: Whether AWS integration tests are enabled
            
    Usage:
        @pytest.mark.aws_integration
        def test_real_sagemaker(aws_integration_config):
            if not aws_integration_config['enabled']:
                pytest.skip("AWS integration tests not enabled")
            
            region = aws_integration_config['region']
            # Use real AWS services
    """
    return {
        'region': request.config.getoption("--aws-region"),
        'profile': request.config.getoption("--aws-profile"),
        'enabled': request.config.getoption("--run-aws-integration"),
    }


@pytest.fixture
def skip_if_no_aws_credentials(aws_integration_config):
    """
    Skip test if AWS credentials are not available.
    
    This fixture checks if AWS credentials are configured and skips
    the test if they are not available.
    
    Usage:
        @pytest.mark.aws_integration
        def test_something(skip_if_no_aws_credentials):
            # Test will be skipped if no credentials
            # Test code here
    """
    import boto3
    from botocore.exceptions import NoCredentialsError, ClientError
    
    if not aws_integration_config['enabled']:
        pytest.skip("AWS integration tests not enabled (use --run-aws-integration)")
    
    try:
        # Try to get credentials
        session = boto3.Session(
            region_name=aws_integration_config['region'],
            profile_name=aws_integration_config['profile']
        )
        credentials = session.get_credentials()
        
        if credentials is None:
            pytest.skip("No AWS credentials available")
        
        # Try to verify credentials work
        sts = session.client('sts')
        sts.get_caller_identity()
        
    except (NoCredentialsError, ClientError) as e:
        pytest.skip(f"AWS credentials not available or invalid: {e}")
