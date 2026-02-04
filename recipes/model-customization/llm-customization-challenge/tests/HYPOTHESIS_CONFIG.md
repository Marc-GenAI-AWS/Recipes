# Hypothesis Configuration Summary

This document summarizes the hypothesis (property-based testing) configuration for the automated LLM finetuning pipeline project.

## Overview

Hypothesis is configured with four profiles to support different testing scenarios:

| Profile | Examples | Deadline | Derandomize | Verbosity | Use Case |
|---------|----------|----------|-------------|-----------|----------|
| `default` | 100 | None | No | Normal | Standard testing (design requirement) |
| `quick` | 20 | None | No | Normal | Fast iteration during development |
| `debug` | 10 | None | Yes | Verbose | Debugging test failures |
| `ci` | 500 | None | No | Normal | Thorough testing in CI/CD |

## Configuration Location

Hypothesis profiles are registered in `tests/conftest.py`:

```python
from hypothesis import settings, Verbosity

# Default profile: Standard testing with 100 examples
settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
    derandomize=False,
    print_blob=True,
)

# CI profile: More thorough testing
settings.register_profile(
    "ci",
    max_examples=500,
    deadline=None,
    derandomize=False,
    print_blob=True,
)

# Debug profile: Fewer examples with verbose output
settings.register_profile(
    "debug",
    max_examples=10,
    verbosity=Verbosity.verbose,
    deadline=None,
    derandomize=True,
    print_blob=True,
)

# Quick profile: Fast iteration
settings.register_profile(
    "quick",
    max_examples=20,
    deadline=None,
    derandomize=False,
    print_blob=False,
)

# Load the default profile
settings.load_profile("default")
```

## Design Requirements

According to the design document (`.kiro/specs/automated-llm-finetuning-pipeline/design.md`):

> **Property-Based Testing**: All property tests MUST use hypothesis with minimum 100 examples (default profile)

This requirement is satisfied by the `default` profile configuration.

## Integration with Pytest

Hypothesis is integrated with pytest through:

1. **pytest.ini**: Specifies the default hypothesis profile
   ```ini
   addopts =
       --hypothesis-profile=default
   ```

2. **conftest.py**: Registers profiles and auto-marks hypothesis tests
   ```python
   def pytest_collection_modifyitems(config, items):
       """Auto-mark tests with hypothesis as property tests."""
       for item in items:
           if "hypothesis" in item.keywords:
               item.add_marker(pytest.mark.property)
               item.add_marker(pytest.mark.pbt)
   ```

3. **Test markers**: Property-based tests are automatically marked with `@pytest.mark.property` and `@pytest.mark.pbt`

## Using Hypothesis Profiles

### Command Line

Run tests with a specific profile:

```bash
# Default profile (100 examples)
pytest tests/property/

# Quick profile (20 examples) - for fast development
pytest tests/property/ --hypothesis-profile=quick

# Debug profile (10 examples, verbose) - for debugging failures
pytest tests/property/ --hypothesis-profile=debug

# CI profile (500 examples) - for thorough CI testing
pytest tests/property/ --hypothesis-profile=ci
```

### In Code

Override profile settings for specific tests:

```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=1000)  # Override for this test only
@given(x=st.integers())
def test_with_more_examples(x):
    assert x == x
```

## Verification

To verify hypothesis is properly configured, run:

```bash
pytest tests/test_hypothesis_config.py -v --hypothesis-show-statistics
```

This test suite verifies:
- ✅ Hypothesis is installed and working
- ✅ All four profiles are registered correctly
- ✅ Property-based tests generate the correct number of examples
- ✅ Different strategies (integers, text, lists) work correctly
- ✅ Profile settings match design requirements

### Example Output

```
tests/test_hypothesis_config.py::test_hypothesis_basic_functionality PASSED
tests/test_hypothesis_config.py::test_hypothesis_text_strategy PASSED
tests/test_hypothesis_config.py::test_hypothesis_list_strategy PASSED
tests/test_hypothesis_config.py::test_hypothesis_constrained_integers PASSED
tests/test_hypothesis_config.py::test_hypothesis_profile_settings PASSED
tests/test_hypothesis_config.py::test_hypothesis_profiles_registered PASSED

======================================== Hypothesis Statistics =========================================

tests/test_hypothesis_config.py::test_hypothesis_basic_functionality:
  - during generate phase (2.27 seconds):
    - Typical runtimes: ~ 0-1 ms, of which < 1ms in data generation
    - 100 passing examples, 0 failing examples, 0 invalid examples
  - Stopped because settings.max_examples=100
```

## Profile Selection Guidelines

### When to Use Each Profile

**Default Profile (100 examples)**
- ✅ Regular development and testing
- ✅ Pre-commit checks
- ✅ Standard test runs
- ✅ Meets design requirements

**Quick Profile (20 examples)**
- ✅ Rapid iteration during development
- ✅ Quick feedback on changes
- ✅ Local testing before committing
- ❌ Not sufficient for final validation

**Debug Profile (10 examples, verbose)**
- ✅ Debugging failing property tests
- ✅ Understanding test behavior
- ✅ Reproducing specific failures
- ❌ Not for regular testing

**CI Profile (500 examples)**
- ✅ Continuous integration pipelines
- ✅ Pre-release validation
- ✅ Thorough testing before deployment
- ❌ Too slow for local development

## Property Test Requirements

All property-based tests in this project must:

1. **Use minimum 100 examples** (default profile)
2. **Be tagged with property number and description**
3. **Include requirement validation comment**
4. **Use appropriate hypothesis strategies**

### Example Property Test

```python
from hypothesis import given, strategies as st
import pytest

# Feature: automated-llm-finetuning-pipeline, Property 1: Use Case Configuration Round-Trip
@pytest.mark.property
@pytest.mark.pbt
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

## Hypothesis Statistics

When running tests with `--hypothesis-show-statistics`, you'll see:

- **Typical runtimes**: How long each example takes
- **Passing/failing/invalid examples**: Test outcome distribution
- **Stop reason**: Why hypothesis stopped generating examples
- **Data generation time**: Time spent generating test data

This information is valuable for:
- Identifying slow tests
- Understanding test coverage
- Debugging test failures
- Optimizing test strategies

## Troubleshooting

### Tests Running Too Slowly

If property tests are too slow:
1. Use `--hypothesis-profile=quick` for development
2. Optimize your hypothesis strategies
3. Use `@settings(max_examples=N)` to reduce examples for specific tests
4. Consider using `deadline=None` to avoid timeout errors

### Flaky Tests

If tests fail intermittently:
1. Use `--hypothesis-profile=debug` to see verbose output
2. Use `--hypothesis-seed=<seed>` to reproduce failures
3. Check if your property assumes ordering or randomness
4. Use `derandomize=True` in debug profile to get consistent examples

### Test Failures

When a property test fails:
1. Hypothesis shows the failing example
2. The example is saved in `.hypothesis/` directory
3. Use `--hypothesis-seed=<seed>` to reproduce
4. Use debug profile for verbose output
5. Simplify the failing example manually if needed

## Additional Resources

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Hypothesis Strategies](https://hypothesis.readthedocs.io/en/latest/data.html)
- [Hypothesis Settings](https://hypothesis.readthedocs.io/en/latest/settings.html)
- [Hypothesis Best Practices](https://hypothesis.readthedocs.io/en/latest/strategies.html)
- [Property-Based Testing Guide](https://hypothesis.works/articles/what-is-property-based-testing/)

## Summary

✅ **Hypothesis is properly configured** with four profiles (default, quick, debug, ci)  
✅ **Default profile uses 100 examples** as required by design  
✅ **Integrated with pytest** through conftest.py and pytest.ini  
✅ **Verified with test suite** (tests/test_hypothesis_config.py)  
✅ **Ready for property-based testing** across all project components  

The configuration meets all design requirements and is ready for implementing the 41 correctness properties specified in the design document.
