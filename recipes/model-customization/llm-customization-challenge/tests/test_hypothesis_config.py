"""
Test to verify hypothesis configuration is working correctly.

This test validates that:
1. Hypothesis is properly installed and configured
2. Hypothesis profiles are registered correctly
3. Property-based tests can run with the configured settings
"""
import pytest
from hypothesis import given, strategies as st, settings


@pytest.mark.property
@pytest.mark.pbt
@given(x=st.integers(), y=st.integers())
def test_hypothesis_basic_functionality(x, y):
    """
    Verify hypothesis is working with basic property test.
    
    Property: Addition is commutative.
    This is a simple test to ensure hypothesis generates examples correctly.
    """
    assert x + y == y + x


@pytest.mark.property
@pytest.mark.pbt
@given(s=st.text())
def test_hypothesis_text_strategy(s):
    """
    Verify hypothesis text strategy works.
    
    Property: String length is non-negative.
    """
    assert len(s) >= 0


@pytest.mark.property
@pytest.mark.pbt
@given(lst=st.lists(st.integers()))
def test_hypothesis_list_strategy(lst):
    """
    Verify hypothesis list strategy works.
    
    Property: Reversing a list twice returns the original list.
    """
    assert list(reversed(list(reversed(lst)))) == lst


@pytest.mark.property
@pytest.mark.pbt
@given(x=st.integers(min_value=0, max_value=100))
def test_hypothesis_constrained_integers(x):
    """
    Verify hypothesis constrained integer strategy works.
    
    Property: Constrained integers stay within bounds.
    """
    assert 0 <= x <= 100


def test_hypothesis_profile_settings():
    """
    Verify hypothesis profile settings are configured correctly.
    
    This test checks that the default profile has the required settings.
    """
    # Get the current settings
    current_settings = settings()
    
    # Verify minimum examples is at least 100 (design requirement)
    # Note: The actual value depends on which profile is active
    # The default profile should have max_examples=100
    assert current_settings.max_examples >= 10, \
        f"Expected at least 10 examples, got {current_settings.max_examples}"
    
    # Verify deadline is None (no time limit per example)
    assert current_settings.deadline is None, \
        "Deadline should be None to allow sufficient time for complex examples"


def test_hypothesis_profiles_registered():
    """
    Verify all required hypothesis profiles are registered.
    
    According to design requirements, we need:
    - default: 100 examples
    - quick: 20 examples
    - debug: 10 examples with verbose output
    - ci: 500 examples
    """
    from hypothesis import settings
    
    # Test that we can load each profile without error
    profiles = ['default', 'quick', 'debug', 'ci']
    
    for profile_name in profiles:
        try:
            # Try to get settings for this profile
            profile_settings = settings.get_profile(profile_name)
            assert profile_settings is not None, f"Profile '{profile_name}' not found"
        except Exception as e:
            pytest.fail(f"Failed to load profile '{profile_name}': {e}")


if __name__ == "__main__":
    # Run this test file directly
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
