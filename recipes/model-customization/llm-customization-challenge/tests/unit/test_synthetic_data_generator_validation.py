"""
Unit tests for SyntheticDataGenerator validation methods.

Tests cover:
- validate_jsonl_format() method
- validate_ascii_compliance() method
- validate_field_completeness() method
- detect_duplicates() method
- remove_duplicates() method
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock

from src.synthetic_data_generator import SyntheticDataGenerator
from src.config_models import PipelineConfig, TrainingExample


@pytest.fixture
def valid_pipeline_config():
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
def mock_bedrock_client():
    """Create a mock Bedrock Runtime client"""
    return Mock()


@pytest.fixture
def generator(mock_bedrock_client, valid_pipeline_config):
    """Create a SyntheticDataGenerator instance for testing"""
    return SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)



class TestValidateJsonlFormat:
    """Test suite for validate_jsonl_format() method"""
    
    def test_validate_valid_jsonl_file(self, generator, tmp_path):
        """Test validation of a valid JSONL file"""
        # Create a valid JSONL file
        jsonl_file = tmp_path / "valid.jsonl"
        with open(jsonl_file, 'w') as f:
            f.write('{"instruction": "Q1", "context": "C1", "response": "R1"}\n')
            f.write('{"instruction": "Q2", "context": "C2", "response": "R2"}\n')
        
        is_valid, errors = generator.validate_jsonl_format(str(jsonl_file))
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_file_not_exists(self, generator, tmp_path):
        """Test validation of non-existent file"""
        non_existent = tmp_path / "does_not_exist.jsonl"
        
        is_valid, errors = generator.validate_jsonl_format(str(non_existent))
        
        assert not is_valid
        assert len(errors) == 1
        assert "does not exist" in errors[0].lower()
    
    def test_validate_empty_file(self, generator, tmp_path):
        """Test validation of empty file"""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.touch()
        
        is_valid, errors = generator.validate_jsonl_format(str(empty_file))
        
        assert not is_valid
        assert len(errors) == 1
        assert "empty" in errors[0].lower()

    
    def test_validate_whitespace_only_file(self, generator, tmp_path):
        """Test validation of file with only whitespace"""
        whitespace_file = tmp_path / "whitespace.jsonl"
        with open(whitespace_file, 'w') as f:
            f.write("   \n\n  \t  \n")
        
        is_valid, errors = generator.validate_jsonl_format(str(whitespace_file))
        
        assert not is_valid
        assert len(errors) == 1
        assert "empty" in errors[0].lower()
    
    def test_validate_invalid_json_line(self, generator, tmp_path):
        """Test validation of file with invalid JSON"""
        invalid_file = tmp_path / "invalid.jsonl"
        with open(invalid_file, 'w') as f:
            f.write('{"instruction": "Q1", "context": "C1", "response": "R1"}\n')
            f.write('not valid json\n')
            f.write('{"instruction": "Q3", "context": "C3", "response": "R3"}\n')
        
        is_valid, errors = generator.validate_jsonl_format(str(invalid_file))
        
        assert not is_valid
        assert len(errors) == 1
        assert "Line 2" in errors[0]
        assert "Invalid JSON" in errors[0]
    
    def test_validate_multiple_invalid_lines(self, generator, tmp_path):
        """Test validation of file with multiple invalid JSON lines"""
        invalid_file = tmp_path / "multiple_invalid.jsonl"
        with open(invalid_file, 'w') as f:
            f.write('{"valid": "json"}\n')
            f.write('invalid line 1\n')
            f.write('{"another": "valid"}\n')
            f.write('invalid line 2\n')
        
        is_valid, errors = generator.validate_jsonl_format(str(invalid_file))
        
        assert not is_valid
        assert len(errors) == 2
        assert any("Line 2" in error for error in errors)
        assert any("Line 4" in error for error in errors)

    
    def test_validate_file_with_empty_lines(self, generator, tmp_path):
        """Test validation of file with empty lines (should be valid)"""
        file_with_empty = tmp_path / "with_empty.jsonl"
        with open(file_with_empty, 'w') as f:
            f.write('{"instruction": "Q1", "context": "C1", "response": "R1"}\n')
            f.write('\n')
            f.write('{"instruction": "Q2", "context": "C2", "response": "R2"}\n')
            f.write('  \n')
            f.write('{"instruction": "Q3", "context": "C3", "response": "R3"}\n')
        
        is_valid, errors = generator.validate_jsonl_format(str(file_with_empty))
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_directory_path(self, generator, tmp_path):
        """Test validation fails when path is a directory"""
        directory = tmp_path / "test_dir"
        directory.mkdir()
        
        is_valid, errors = generator.validate_jsonl_format(str(directory))
        
        assert not is_valid
        assert len(errors) == 1
        assert "not a file" in errors[0].lower()
    
    def test_validate_malformed_json_missing_bracket(self, generator, tmp_path):
        """Test validation of JSON with missing closing bracket"""
        malformed_file = tmp_path / "malformed.jsonl"
        with open(malformed_file, 'w') as f:
            f.write('{"instruction": "Q1", "context": "C1"\n')
        
        is_valid, errors = generator.validate_jsonl_format(str(malformed_file))
        
        assert not is_valid
        assert len(errors) >= 1
        assert "Invalid JSON" in errors[0]


class TestValidateAsciiCompliance:
    """Test suite for validate_ascii_compliance() method"""
    
    def test_validate_pure_ascii_text(self, generator):
        """Test validation of pure ASCII text"""
        text = "Hello world! This is ASCII text."
        
        is_compliant, issues = generator.validate_ascii_compliance(text)
        
        assert is_compliant
        assert len(issues) == 0

    
    def test_validate_text_with_unicode(self, generator):
        """Test validation of text with unicode characters"""
        text = "Café résumé naïve"
        
        is_compliant, issues = generator.validate_ascii_compliance(text)
        
        assert not is_compliant
        assert len(issues) > 0
        assert "non-ASCII" in issues[0]
    
    def test_validate_empty_string(self, generator):
        """Test validation of empty string"""
        is_compliant, issues = generator.validate_ascii_compliance("")
        
        assert is_compliant
        assert len(issues) == 0
    
    def test_validate_none_string(self, generator):
        """Test validation of None"""
        is_compliant, issues = generator.validate_ascii_compliance(None)
        
        assert is_compliant
        assert len(issues) == 0
    
    def test_validate_text_with_emoji(self, generator):
        """Test validation of text with emoji"""
        text = "Hello 👋 world 🌍"
        
        is_compliant, issues = generator.validate_ascii_compliance(text)
        
        assert not is_compliant
        assert len(issues) > 0
    
    def test_validate_text_with_chinese_characters(self, generator):
        """Test validation of text with Chinese characters"""
        text = "Hello 你好 world"
        
        is_compliant, issues = generator.validate_ascii_compliance(text)
        
        assert not is_compliant
        assert len(issues) > 0
    
    def test_validate_ascii_with_numbers_and_symbols(self, generator):
        """Test validation of ASCII text with numbers and symbols"""
        text = "Test123!@#$%^&*()_+-=[]{}|;':\",./<>?"
        
        is_compliant, issues = generator.validate_ascii_compliance(text)
        
        assert is_compliant
        assert len(issues) == 0

    
    def test_validate_ascii_with_newlines_and_tabs(self, generator):
        """Test validation of ASCII text with newlines and tabs"""
        text = "Line 1\nLine 2\tTabbed"
        
        is_compliant, issues = generator.validate_ascii_compliance(text)
        
        assert is_compliant
        assert len(issues) == 0
    
    def test_validate_reports_specific_characters(self, generator):
        """Test that validation reports specific non-ASCII characters"""
        text = "Café"
        
        is_compliant, issues = generator.validate_ascii_compliance(text)
        
        assert not is_compliant
        assert len(issues) > 0
        # Should mention the specific character
        assert "é" in issues[0] or "'\\xe9'" in issues[0]


class TestValidateFieldCompleteness:
    """Test suite for validate_field_completeness() method"""
    
    def test_validate_complete_example(self, generator):
        """Test validation of complete training example"""
        example = {
            "instruction": "Help the user",
            "context": "User needs assistance",
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert is_complete
        assert len(errors) == 0
    
    def test_validate_missing_instruction(self, generator):
        """Test validation of example missing instruction field"""
        example = {
            "context": "User needs assistance",
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert len(errors) >= 1
        assert any("instruction" in error.lower() for error in errors)

    
    def test_validate_missing_context(self, generator):
        """Test validation of example missing context field"""
        example = {
            "instruction": "Help the user",
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert len(errors) >= 1
        assert any("context" in error.lower() for error in errors)
    
    def test_validate_missing_response(self, generator):
        """Test validation of example missing response field"""
        example = {
            "instruction": "Help the user",
            "context": "User needs assistance"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert len(errors) >= 1
        assert any("response" in error.lower() for error in errors)
    
    def test_validate_missing_all_fields(self, generator):
        """Test validation of example missing all fields"""
        example = {}
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert len(errors) == 3
        assert any("instruction" in error.lower() for error in errors)
        assert any("context" in error.lower() for error in errors)
        assert any("response" in error.lower() for error in errors)
    
    def test_validate_empty_instruction(self, generator):
        """Test validation of example with empty instruction"""
        example = {
            "instruction": "",
            "context": "User needs assistance",
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert any("instruction" in error.lower() and "empty" in error.lower() 
                  for error in errors)

    
    def test_validate_whitespace_only_instruction(self, generator):
        """Test validation of example with whitespace-only instruction"""
        example = {
            "instruction": "   ",
            "context": "User needs assistance",
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert any("instruction" in error.lower() for error in errors)
    
    def test_validate_empty_response(self, generator):
        """Test validation of example with empty response"""
        example = {
            "instruction": "Help the user",
            "context": "User needs assistance",
            "response": ""
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert any("response" in error.lower() and "empty" in error.lower() 
                  for error in errors)
    
    def test_validate_empty_context_allowed(self, generator):
        """Test that empty context is allowed"""
        example = {
            "instruction": "Help the user",
            "context": "",
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert is_complete
        assert len(errors) == 0
    
    def test_validate_non_string_instruction(self, generator):
        """Test validation of example with non-string instruction"""
        example = {
            "instruction": 123,
            "context": "User needs assistance",
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert any("instruction" in error.lower() and "string" in error.lower() 
                  for error in errors)

    
    def test_validate_non_string_context(self, generator):
        """Test validation of example with non-string context"""
        example = {
            "instruction": "Help the user",
            "context": ["list", "not", "string"],
            "response": "I'm here to help"
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert any("context" in error.lower() and "string" in error.lower() 
                  for error in errors)
    
    def test_validate_non_string_response(self, generator):
        """Test validation of example with non-string response"""
        example = {
            "instruction": "Help the user",
            "context": "User needs assistance",
            "response": {"key": "value"}
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert any("response" in error.lower() and "string" in error.lower() 
                  for error in errors)
    
    def test_validate_multiple_errors(self, generator):
        """Test validation reports multiple errors"""
        example = {
            "instruction": "",
            "context": 123,
            "response": None
        }
        
        is_complete, errors = generator.validate_field_completeness(example)
        
        assert not is_complete
        assert len(errors) >= 3


class TestDetectDuplicates:
    """Test suite for detect_duplicates() method"""
    
    def test_detect_no_duplicates(self, generator):
        """Test detection with no duplicates"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q3", "C3", "R3"),
        ]
        
        duplicates = generator.detect_duplicates(examples)
        
        assert len(duplicates) == 0

    
    def test_detect_one_duplicate_pair(self, generator):
        """Test detection of one duplicate pair"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q1", "C1", "R1"),  # Duplicate of index 0
        ]
        
        duplicates = generator.detect_duplicates(examples)
        
        assert len(duplicates) == 1
        assert (0, 2) in duplicates
    
    def test_detect_multiple_duplicates(self, generator):
        """Test detection of multiple duplicates"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q1", "C1", "R1"),  # Duplicate of 0
            TrainingExample("Q2", "C2", "R2"),  # Duplicate of 1
        ]
        
        duplicates = generator.detect_duplicates(examples)
        
        assert len(duplicates) == 2
        assert (0, 2) in duplicates
        assert (1, 3) in duplicates
    
    def test_detect_triple_duplicate(self, generator):
        """Test detection when same example appears three times"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q1", "C1", "R1"),  # Duplicate of 0
            TrainingExample("Q1", "C1", "R1"),  # Duplicate of 0 and 1
        ]
        
        duplicates = generator.detect_duplicates(examples)
        
        # Should report (0,1) and (0,2) and (1,2)
        assert len(duplicates) == 3
        assert (0, 1) in duplicates
        assert (0, 2) in duplicates
        assert (1, 2) in duplicates
    
    def test_detect_empty_list(self, generator):
        """Test detection with empty list"""
        examples = []
        
        duplicates = generator.detect_duplicates(examples)
        
        assert len(duplicates) == 0

    
    def test_detect_similar_but_not_duplicate(self, generator):
        """Test that similar but different examples are not detected as duplicates"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q1", "C1", "R2"),  # Different response
            TrainingExample("Q1", "C2", "R1"),  # Different context
            TrainingExample("Q2", "C1", "R1"),  # Different instruction
        ]
        
        duplicates = generator.detect_duplicates(examples)
        
        assert len(duplicates) == 0
    
    def test_detect_preserves_order(self, generator):
        """Test that duplicate pairs maintain index order (i < j)"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q1", "C1", "R1"),
        ]
        
        duplicates = generator.detect_duplicates(examples)
        
        for i, j in duplicates:
            assert i < j


class TestRemoveDuplicates:
    """Test suite for remove_duplicates() method"""
    
    def test_remove_no_duplicates(self, generator):
        """Test removal with no duplicates"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q3", "C3", "R3"),
        ]
        
        unique = generator.remove_duplicates(examples)
        
        assert len(unique) == 3
        assert unique == examples
    
    def test_remove_one_duplicate(self, generator):
        """Test removal of one duplicate"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q1", "C1", "R1"),  # Duplicate
        ]
        
        unique = generator.remove_duplicates(examples)
        
        assert len(unique) == 2
        assert unique[0].instruction == "Q1"
        assert unique[1].instruction == "Q2"

    
    def test_remove_multiple_duplicates(self, generator):
        """Test removal of multiple duplicates"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q1", "C1", "R1"),  # Duplicate
            TrainingExample("Q3", "C3", "R3"),
            TrainingExample("Q2", "C2", "R2"),  # Duplicate
        ]
        
        unique = generator.remove_duplicates(examples)
        
        assert len(unique) == 3
        assert unique[0].instruction == "Q1"
        assert unique[1].instruction == "Q2"
        assert unique[2].instruction == "Q3"
    
    def test_remove_preserves_first_occurrence(self, generator):
        """Test that first occurrence is preserved"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q1", "C1", "R1"),
        ]
        
        unique = generator.remove_duplicates(examples)
        
        # First Q1 should be at index 0
        assert unique[0] is examples[0]
        assert unique[1] is examples[1]
    
    def test_remove_empty_list(self, generator):
        """Test removal with empty list"""
        examples = []
        
        unique = generator.remove_duplicates(examples)
        
        assert len(unique) == 0
    
    def test_remove_all_duplicates(self, generator):
        """Test removal when all examples are duplicates"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q1", "C1", "R1"),
        ]
        
        unique = generator.remove_duplicates(examples)
        
        assert len(unique) == 1
        assert unique[0].instruction == "Q1"
    
    def test_remove_does_not_modify_original(self, generator):
        """Test that original list is not modified"""
        examples = [
            TrainingExample("Q1", "C1", "R1"),
            TrainingExample("Q2", "C2", "R2"),
            TrainingExample("Q1", "C1", "R1"),
        ]
        original_length = len(examples)
        
        unique = generator.remove_duplicates(examples)
        
        assert len(examples) == original_length
        assert len(unique) != len(examples)
