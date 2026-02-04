# Tests Directory

This directory contains all tests for the automated LLM finetuning pipeline.

## Structure

- **unit/**: Unit tests for individual components and functions
- **property/**: Property-based tests using hypothesis
- **integration/**: Integration tests for component interactions
- **fixtures/**: Test fixtures including sample data and mock responses

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only property-based tests
pytest tests/property/

# Run with coverage
pytest --cov=src --cov-report=html

# Run integration tests (requires AWS credentials)
pytest -m integration
```

## Test Requirements

- Unit test coverage: >80% of code
- All 41 correctness properties must be implemented
- Property tests should use minimum 100 examples
- Integration tests should be marked with @pytest.mark.integration
