# Testing Guide for Automated LLM Finetuning Pipeline

This document describes the testing strategy, configuration, and best practices for the automated LLM finetuning pipeline project.

## Table of Contents

1. [Testing Strategy](#testing-strategy)
2. [Test Configuration](#test-configuration)
3. [Running Tests](#running-tests)
4. [Test Markers](#test-markers)
5. [Property-Based Testing](#property-based-testing)
6. [Writing Tests](#writing-tests)
7. [Coverage Requirements](#coverage-requirements)

## Testing Strategy

The project uses a **dual testing approach** combining:

1. **Unit Tests**: Test specific examples, edge cases, and integration points
2. **Property-Based Tests (PBT)**: Test universal properties across many generated inputs

This approach ensures both specific scenarios work correctly and general properties hold across all inputs.

### Test Organization

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── test_pytest_config.py    # Configuration verification tests
├── unit/                    # Unit tests for individual components
│   ├── test_configuration_manager.py
│   ├── test_synthetic_data_generator.py
│   ├── test_model_trainer.py
│   ├── test_model_deployer.py
│   ├── test_inference_engine.py
│   ├── test_judge.py
│   ├── test_self_improvement_agent.py
│   ├── test_progress_tracker.py
│   ├── test_pipeline_orchestrator.py
│   └── test_streamlit_ui.py
├── property/                # Property-based tests
│   ├── test_configuration_properties.py
│   ├── test_data_generation_properties.py
│   ├── test_evaluation_properties.py
│   ├── test_tracking_properties.py
│   ├── test_pipeline_properties.py
│   └── test_ui_properties.py
├── integration/             # Integration tests
│   ├── test_end_to_end_pipeline.py
│   ├── test_aws_integration.py
│   └── test_ui_integration.py
└── fixtures/                # Test data and fixtures
    ├── sample_use_cases.yaml
    ├── sample_training_data.jsonl
    └── mock_responses.json
```

## Test Configuration

### pytest.ini

The main pytest configuration file (`pytest.ini`) defines:

- **Test discovery patterns**: Where to find tests and how to identify them
- **Test markers**: Categories for organizing and filtering tests
- **Coverage settings**: Code coverage targets and reporting
- **Logging configuration**: How test logs are captured and displayed
- **Hypothesis integration**: Property-based testing configuration

### conftest.py

The `tests/conftest.py` file provides:

- **Hypothesis profiles**: Different configurations for various testing scenarios
- **Common fixtures**: Reusable test fixtures for temporary directories, mock objects, etc.
- **AWS mocking fixtures**: Fixtures for mocking AWS services (SageMaker, S3, Bedrock) using moto
- **Test hooks**: Automatic marker application and test collection customization

### AWS Service Mocking

The project uses [moto](https://docs.getmoto.org/) to mock AWS services for testing. This allows testing AWS integrations without:
- Making real API calls
- Incurring AWS costs
- Requiring AWS credentials
- Dealing with network latency

**Available AWS Fixtures**:
- `mock_sagemaker`: Mock SageMaker service
- `mock_s3`: Mock S3 service
- `mock_bedrock`: Mock Bedrock Runtime service
- `mock_aws_services`: Mock all AWS services at once
- `mock_sagemaker_with_role`: Mock SageMaker with pre-configured IAM role
- `mock_s3_with_bucket`: Mock S3 with pre-created bucket
- `aws_client_manager_with_mocks`: AWSClientManager configured with moto

**See the [AWS Mocking Guide](AWS_MOCKING_GUIDE.md) for detailed documentation and examples.**

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Tests in a Specific Directory

```bash
pytest tests/unit/
pytest tests/property/
pytest tests/integration/
```

### Run a Specific Test File

```bash
pytest tests/unit/test_configuration_manager.py
```

### Run a Specific Test

```bash
pytest tests/unit/test_configuration_manager.py::test_load_use_case
```

### Run Tests with Coverage

First, install pytest-cov:
```bash
pip install pytest-cov
```

Then uncomment the coverage options in `pytest.ini` under the `addopts` section, or run:
```bash
pytest --cov=src --cov-report=html --cov-report=term-missing
```

View the HTML coverage report:
```bash
# Open htmlcov/index.html in your browser
```

## Test Markers

Tests can be marked with categories to enable selective test execution.

### Available Markers

- `@pytest.mark.unit`: Unit tests for individual components
- `@pytest.mark.property`: Property-based tests using hypothesis
- `@pytest.mark.pbt`: Alias for property marker
- `@pytest.mark.integration`: Integration tests requiring AWS services
- `@pytest.mark.slow`: Tests that take significant time to run
- `@pytest.mark.aws`: Tests that interact with real AWS services
- `@pytest.mark.ui`: Tests for Streamlit UI components

### Running Tests by Marker

Run only unit tests:
```bash
pytest -m unit
```

Run only property-based tests:
```bash
pytest -m property
# or
pytest -m pbt
```

Run all tests except integration tests:
```bash
pytest -m "not integration"
```

Run unit and property tests, but not integration:
```bash
pytest -m "unit or property"
```

Run only slow tests:
```bash
pytest -m slow
```

### Skipping Tests

Skip integration tests that require AWS credentials:
```bash
pytest -m "not aws"
```

## Property-Based Testing

Property-based testing uses the [Hypothesis](https://hypothesis.readthedocs.io/) library to generate many test cases automatically.

### Hypothesis Profiles

Different profiles control how many examples are generated:

| Profile | Examples | Use Case |
|---------|----------|----------|
| `default` | 100 | Standard testing (design requirement) |
| `quick` | 20 | Fast iteration during development |
| `debug` | 10 | Debugging test failures with verbose output |
| `ci` | 500 | Thorough testing in CI/CD pipelines |

### Using Hypothesis Profiles

Run tests with a specific profile:
```bash
pytest --hypothesis-profile=quick
pytest --hypothesis-profile=debug
pytest --hypothesis-profile=ci
```

### View Hypothesis Statistics

See detailed statistics about property test execution:
```bash
pytest --hypothesis-show-statistics
```

### Example Property-Based Test

```python
from hypothesis import given, strategies as st
import pytest

@pytest.mark.property
@given(x=st.integers(), y=st.integers())
def test_addition_commutative(x, y):
    """Property: Addition is commutative."""
    assert x + y == y + x
```

### Property Test Requirements

According to the design document, all property-based tests must:

1. Use minimum 100 examples (default profile)
2. Be tagged with the property number and description
3. Include a comment linking to the requirement being validated

Example:
```python
# Feature: automated-llm-finetuning-pipeline, Property 1: Use Case Configuration Round-Trip
@pytest.mark.property
@given(use_case=use_case_strategy())
def test_use_case_round_trip(use_case):
    """
    For any valid use case, storing and loading should preserve all fields.
    
    Validates: Requirements 1.1
    """
    config_manager = ConfigurationManager()
    config_manager.save_use_case(use_case)
    loaded = config_manager.load_use_case(use_case.name)
    assert loaded == use_case
```

## Writing Tests

### Unit Test Example

```python
import pytest
from src.configuration_manager import ConfigurationManager

class TestConfigurationManager:
    """Unit tests for ConfigurationManager."""
    
    @pytest.mark.unit
    def test_load_use_case_success(self, temp_config_dir):
        """Test loading a valid use case."""
        # Arrange
        config_manager = ConfigurationManager(str(temp_config_dir))
        # ... setup test data
        
        # Act
        use_case = config_manager.load_use_case("test_case")
        
        # Assert
        assert use_case.name == "test_case"
        assert use_case.description != ""
    
    @pytest.mark.unit
    def test_load_use_case_not_found(self, temp_config_dir):
        """Test loading a non-existent use case raises error."""
        config_manager = ConfigurationManager(str(temp_config_dir))
        
        with pytest.raises(FileNotFoundError):
            config_manager.load_use_case("nonexistent")
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
@pytest.mark.slow
def test_end_to_end_pipeline(mock_aws_services):
    """Test complete pipeline execution with mocked AWS services."""
    # This test requires mocked AWS services
    # Mark as integration and slow
    pass

@pytest.mark.integration
@pytest.mark.aws
@pytest.mark.skip(reason="Requires AWS credentials")
def test_real_sagemaker_training():
    """Test actual SageMaker training (requires credentials)."""
    # This test uses real AWS services
    # Skip by default, run manually when needed
    pass
```

### Using Fixtures

```python
def test_with_temp_directories(temp_config_dir, temp_event_files_dir):
    """Test using temporary directories."""
    # temp_config_dir and temp_event_files_dir are automatically created
    # and cleaned up after the test
    config_file = temp_config_dir / "test.yaml"
    config_file.write_text("test: data")
    assert config_file.exists()
```

## Coverage Requirements

### Coverage Goals

- **Overall coverage**: >80% (enforced when coverage options are enabled)
- **Unit test coverage**: >80% of code
- **Property test coverage**: All 41 correctness properties implemented
- **Integration test coverage**: All major component interactions
- **Error path coverage**: All error handling paths tested

### Checking Coverage

1. Enable coverage in `pytest.ini` (uncomment coverage options in `addopts`)
2. Run tests with coverage:
   ```bash
   pytest
   ```
3. View coverage report:
   ```bash
   # Terminal report is shown automatically
   # Open HTML report: htmlcov/index.html
   ```

### Coverage Exclusions

The following are excluded from coverage requirements:
- Test files
- Virtual environment
- `__pycache__` directories
- Abstract methods
- Type checking blocks (`if TYPE_CHECKING:`)
- Debug-only code (`def __repr__`)
- Defensive assertions that should never be hit

## Best Practices

### Test Naming

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Use descriptive names that explain what is being tested

### Test Structure

Follow the Arrange-Act-Assert pattern:
```python
def test_example():
    # Arrange: Set up test data and conditions
    data = create_test_data()
    
    # Act: Execute the code being tested
    result = function_under_test(data)
    
    # Assert: Verify the results
    assert result == expected_value
```

### Test Independence

- Each test should be independent and not rely on other tests
- Use fixtures for shared setup
- Clean up resources after tests (fixtures handle this automatically)

### Mocking

- Mock external dependencies (AWS services, file I/O, network calls)
- Use `moto` for mocking AWS services (see [AWS Mocking Guide](AWS_MOCKING_GUIDE.md))
- Use `pytest.monkeypatch` for simple mocking
- Use the provided AWS fixtures for consistent mocking patterns

Example with moto:
```python
def test_s3_upload(mock_s3_with_bucket):
    """Test S3 upload with mocked service."""
    bucket_name = mock_s3_with_bucket
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Upload file - all calls are mocked
    s3.put_object(Bucket=bucket_name, Key='test.txt', Body=b'data')
    
    # Verify upload
    response = s3.get_object(Bucket=bucket_name, Key='test.txt')
    assert response['Body'].read() == b'data'
```

### Error Testing

Test both success and failure cases:
```python
def test_success_case():
    """Test the happy path."""
    result = function()
    assert result.success

def test_error_case():
    """Test error handling."""
    with pytest.raises(ValueError, match="Invalid input"):
        function(invalid_input)
```

## Continuous Integration

For CI/CD pipelines, use the `ci` hypothesis profile for more thorough testing:

```bash
pytest --hypothesis-profile=ci -m "not aws"
```

This runs:
- All unit tests
- All property tests with 500 examples each
- All integration tests that don't require real AWS credentials
- Excludes tests marked with `@pytest.mark.aws`

## Troubleshooting

### Tests Not Found

If pytest doesn't find your tests:
1. Check that test files start with `test_`
2. Check that test functions start with `test_`
3. Verify you're in the project root directory
4. Run `pytest --collect-only` to see what tests are discovered

### Hypothesis Test Failures

If a property test fails:
1. Hypothesis will show the failing example
2. Run with `--hypothesis-profile=debug` for verbose output
3. Use `--hypothesis-seed=<seed>` to reproduce the exact failure
4. The failing example is saved in `.hypothesis/` directory

### Coverage Not Working

If coverage reports aren't generated:
1. Ensure `pytest-cov` is installed: `pip install pytest-cov`
2. Uncomment coverage options in `pytest.ini`
3. Or run with explicit coverage flags: `pytest --cov=src`

### Slow Tests

If tests are too slow:
1. Use `pytest -m "not slow"` to skip slow tests
2. Use `--hypothesis-profile=quick` for faster property tests
3. Run specific test files instead of the entire suite
4. Consider parallelizing tests with `pytest-xdist`

## Verifying Configuration

To verify that hypothesis and pytest are properly configured, run the configuration tests:

```bash
pytest tests/test_hypothesis_config.py -v
```

This will verify:
- Hypothesis is installed and working
- All profiles (default, quick, debug, ci) are registered correctly
- Property-based tests generate the correct number of examples
- Test markers are properly configured

To test different profiles:
```bash
# Test with quick profile (20 examples)
pytest tests/test_hypothesis_config.py --hypothesis-profile=quick

# Test with debug profile (10 examples, verbose)
pytest tests/test_hypothesis_config.py --hypothesis-profile=debug

# Test with ci profile (500 examples)
pytest tests/test_hypothesis_config.py --hypothesis-profile=ci
```

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Moto Documentation](http://docs.getmoto.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [AWS Mocking Guide](AWS_MOCKING_GUIDE.md) - Comprehensive guide for mocking AWS services in tests
