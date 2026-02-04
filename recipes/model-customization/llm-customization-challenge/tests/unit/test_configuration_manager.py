"""
Unit Tests for ConfigurationManager

Tests the ConfigurationManager class functionality including:
- Initialization with config directory
- Directory structure creation
- Configuration loading and saving
- Validation logic
- Use case management
"""

import os
import pytest
import tempfile
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.configuration_manager import ConfigurationManager
from src.config_models import UseCase, PipelineConfig, ValidationResult


class TestConfigurationManagerInit:
    """Test suite for ConfigurationManager.__init__"""
    
    def test_init_with_default_config_dir(self, tmp_path):
        """Test initialization with default config directory"""
        # Change to temp directory to avoid creating config/ in project root
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            config_manager = ConfigurationManager()
            
            # Verify config_dir is set correctly
            assert config_manager.config_dir.name == "config"
            assert config_manager.config_dir.exists()
            
            # Verify use_cases_dir is set correctly
            assert config_manager.use_cases_dir.name == "use_cases"
            assert config_manager.use_cases_dir.exists()
            
            # Verify pipeline_config_path is set
            assert config_manager.pipeline_config_path.name == "pipeline_config.yaml"
            
        finally:
            os.chdir(original_cwd)
    
    def test_init_with_custom_config_dir(self, tmp_path):
        """Test initialization with custom config directory"""
        custom_dir = tmp_path / "custom_config"
        
        config_manager = ConfigurationManager(str(custom_dir))
        
        # Verify custom directory is used
        assert config_manager.config_dir == custom_dir.resolve()
        assert config_manager.config_dir.exists()
        
        # Verify subdirectories are created
        assert config_manager.use_cases_dir.exists()
        assert config_manager.use_cases_dir == custom_dir / "use_cases"
    
    def test_init_creates_directory_structure(self, tmp_path):
        """Test that initialization creates required directory structure"""
        config_dir = tmp_path / "new_config"
        
        # Verify directory doesn't exist yet
        assert not config_dir.exists()
        
        config_manager = ConfigurationManager(str(config_dir))
        
        # Verify directories were created
        assert config_dir.exists()
        assert (config_dir / "use_cases").exists()
        assert config_manager.config_dir.is_dir()
        assert config_manager.use_cases_dir.is_dir()
    
    def test_init_with_existing_directory(self, tmp_path):
        """Test initialization with existing config directory"""
        config_dir = tmp_path / "existing_config"
        config_dir.mkdir()
        use_cases_dir = config_dir / "use_cases"
        use_cases_dir.mkdir()
        
        # Create a test file to ensure existing content is preserved
        test_file = use_cases_dir / "test.yaml"
        test_file.write_text("test: data")
        
        config_manager = ConfigurationManager(str(config_dir))
        
        # Verify existing directory is used
        assert config_manager.config_dir == config_dir.resolve()
        
        # Verify existing content is preserved
        assert test_file.exists()
        assert test_file.read_text() == "test: data"
    
    def test_init_with_relative_path(self, tmp_path):
        """Test initialization with relative path"""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            config_manager = ConfigurationManager("./my_config")
            
            # Verify path is resolved to absolute
            assert config_manager.config_dir.is_absolute()
            assert config_manager.config_dir.exists()
            assert config_manager.config_dir.name == "my_config"
            
        finally:
            os.chdir(original_cwd)
    
    def test_init_with_trailing_slash(self, tmp_path):
        """Test initialization handles trailing slash correctly"""
        config_dir = tmp_path / "config_with_slash"
        
        # Test with trailing slash
        config_manager = ConfigurationManager(str(config_dir) + "/")
        
        assert config_manager.config_dir.exists()
        assert config_manager.use_cases_dir.exists()
    
    def test_init_with_whitespace_in_path(self, tmp_path):
        """Test initialization with whitespace in directory name"""
        config_dir = tmp_path / "config with spaces"
        
        config_manager = ConfigurationManager(str(config_dir))
        
        assert config_manager.config_dir.exists()
        assert config_manager.use_cases_dir.exists()
        assert "config with spaces" in str(config_manager.config_dir)
    
    def test_init_normalizes_path(self, tmp_path):
        """Test that initialization normalizes path (removes extra slashes, etc.)"""
        config_dir = tmp_path / "config"
        
        # Create path with redundant elements
        messy_path = str(config_dir) + "//subdir//..//"
        
        config_manager = ConfigurationManager(messy_path)
        
        # Verify path is normalized
        assert config_manager.config_dir.exists()
        assert "//" not in str(config_manager.config_dir)
    
    def test_init_with_empty_string_raises_error(self):
        """Test that empty config_dir raises ValueError"""
        with pytest.raises(ValueError, match="config_dir cannot be empty"):
            ConfigurationManager("")
    
    def test_init_with_whitespace_only_raises_error(self):
        """Test that whitespace-only config_dir raises ValueError"""
        with pytest.raises(ValueError, match="config_dir cannot be empty"):
            ConfigurationManager("   ")
    
    def test_init_with_none_raises_error(self):
        """Test that None config_dir raises appropriate error"""
        with pytest.raises((ValueError, TypeError)):
            ConfigurationManager(None)
    
    def test_init_creates_nested_directories(self, tmp_path):
        """Test initialization creates nested directory structure"""
        nested_dir = tmp_path / "level1" / "level2" / "config"
        
        config_manager = ConfigurationManager(str(nested_dir))
        
        # Verify all levels are created
        assert nested_dir.exists()
        assert (nested_dir / "use_cases").exists()
    
    def test_init_sets_pipeline_config_path(self, tmp_path):
        """Test that initialization sets pipeline_config_path correctly"""
        config_dir = tmp_path / "config"
        
        config_manager = ConfigurationManager(str(config_dir))
        
        expected_path = config_dir / "pipeline_config.yaml"
        assert config_manager.pipeline_config_path == expected_path
    
    def test_init_logs_initialization(self, tmp_path, caplog):
        """Test that initialization logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        config_dir = tmp_path / "config"
        
        config_manager = ConfigurationManager(str(config_dir))
        
        # Verify log messages
        assert "ConfigurationManager initialized" in caplog.text
        assert str(config_dir) in caplog.text
    
    def test_init_with_permission_error(self, tmp_path):
        """Test initialization handles permission errors gracefully"""
        config_dir = tmp_path / "readonly_config"
        config_dir.mkdir()
        
        # Make directory read-only (Unix-like systems)
        if os.name != 'nt':  # Skip on Windows
            os.chmod(config_dir, 0o444)
            
            try:
                with pytest.raises(OSError, match="Failed to create configuration directories"):
                    # Try to create subdirectory in read-only directory
                    ConfigurationManager(str(config_dir / "subdir"))
            finally:
                # Restore permissions for cleanup
                os.chmod(config_dir, 0o755)
    
    def test_init_multiple_instances_same_directory(self, tmp_path):
        """Test that multiple instances can use the same directory"""
        config_dir = tmp_path / "shared_config"
        
        config_manager1 = ConfigurationManager(str(config_dir))
        config_manager2 = ConfigurationManager(str(config_dir))
        
        # Both should work without conflicts
        assert config_manager1.config_dir == config_manager2.config_dir
        assert config_manager1.use_cases_dir == config_manager2.use_cases_dir
    
    def test_init_preserves_existing_files(self, tmp_path):
        """Test that initialization doesn't delete existing files"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create some existing files
        existing_file = config_dir / "existing.yaml"
        existing_file.write_text("existing: content")
        
        use_cases_dir = config_dir / "use_cases"
        use_cases_dir.mkdir()
        use_case_file = use_cases_dir / "use_case.yaml"
        use_case_file.write_text("use_case: data")
        
        # Initialize ConfigurationManager
        config_manager = ConfigurationManager(str(config_dir))
        
        # Verify existing files are preserved
        assert existing_file.exists()
        assert existing_file.read_text() == "existing: content"
        assert use_case_file.exists()
        assert use_case_file.read_text() == "use_case: data"
    
    def test_init_config_dir_is_path_object(self, tmp_path):
        """Test that config_dir is stored as Path object"""
        config_dir = tmp_path / "config"
        
        config_manager = ConfigurationManager(str(config_dir))
        
        assert isinstance(config_manager.config_dir, Path)
        assert isinstance(config_manager.use_cases_dir, Path)
        assert isinstance(config_manager.pipeline_config_path, Path)
    
    def test_init_config_dir_is_absolute(self, tmp_path):
        """Test that config_dir is converted to absolute path"""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Use relative path
            config_manager = ConfigurationManager("relative_config")
            
            # Verify it's converted to absolute
            assert config_manager.config_dir.is_absolute()
            
        finally:
            os.chdir(original_cwd)


class TestConfigurationManagerAttributes:
    """Test suite for ConfigurationManager attributes"""
    
    def test_config_dir_attribute(self, tmp_path):
        """Test config_dir attribute is accessible"""
        config_dir = tmp_path / "config"
        config_manager = ConfigurationManager(str(config_dir))
        
        assert hasattr(config_manager, 'config_dir')
        assert config_manager.config_dir == config_dir.resolve()
    
    def test_use_cases_dir_attribute(self, tmp_path):
        """Test use_cases_dir attribute is accessible"""
        config_dir = tmp_path / "config"
        config_manager = ConfigurationManager(str(config_dir))
        
        assert hasattr(config_manager, 'use_cases_dir')
        assert config_manager.use_cases_dir == config_dir / "use_cases"
    
    def test_pipeline_config_path_attribute(self, tmp_path):
        """Test pipeline_config_path attribute is accessible"""
        config_dir = tmp_path / "config"
        config_manager = ConfigurationManager(str(config_dir))
        
        assert hasattr(config_manager, 'pipeline_config_path')
        assert config_manager.pipeline_config_path == config_dir / "pipeline_config.yaml"


# Pytest fixtures
@pytest.fixture
def temp_config_dir(tmp_path):
    """Fixture providing a temporary config directory"""
    config_dir = tmp_path / "test_config"
    yield config_dir
    # Cleanup is automatic with tmp_path


@pytest.fixture
def config_manager(temp_config_dir):
    """Fixture providing a ConfigurationManager instance"""
    return ConfigurationManager(str(temp_config_dir))


@pytest.fixture
def sample_use_case_yaml():
    """Fixture providing sample use case YAML content"""
    return """
name: test_use_case
description: A test use case for unit testing
test_questions:
  - "What is the capital of France?"
  - "How do I reset my password?"
  - "What are your business hours?"
judge_criteria: |
  Evaluate responses based on accuracy and helpfulness.
data_generation_prompt: |
  Generate training examples for customer support.
judge_prompt: |
  Compare the two responses and determine which is better.
version: 1
created_at: 2024-01-15T10:30:00Z
"""


@pytest.fixture
def create_use_case_file(temp_config_dir, sample_use_case_yaml):
    """Fixture that creates a use case YAML file"""
    def _create_file(name="test_use_case", content=None):
        use_cases_dir = temp_config_dir / "use_cases"
        use_cases_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = use_cases_dir / f"{name}.yaml"
        # Use UTF-8 encoding explicitly to handle Unicode characters
        file_path.write_text(content or sample_use_case_yaml, encoding='utf-8')
        return file_path
    
    return _create_file


class TestConfigurationManagerLoadUseCase:
    """Test suite for ConfigurationManager.load_use_case()"""
    
    def test_load_use_case_basic(self, config_manager, create_use_case_file):
        """Test loading a basic use case"""
        create_use_case_file("customer_support")
        
        use_case = config_manager.load_use_case("customer_support")
        
        assert use_case.name == "test_use_case"
        assert use_case.description == "A test use case for unit testing"
        assert len(use_case.test_questions) == 3
        assert use_case.test_questions[0] == "What is the capital of France?"
        assert "accuracy and helpfulness" in use_case.judge_criteria
        assert "training examples" in use_case.data_generation_prompt
        assert "Compare the two responses" in use_case.judge_prompt
        assert use_case.version == 1
    
    def test_load_use_case_with_yaml_extension(self, config_manager, create_use_case_file):
        """Test loading use case with .yaml extension in name"""
        create_use_case_file("test_case")
        
        use_case = config_manager.load_use_case("test_case.yaml")
        
        assert use_case.name == "test_use_case"
    
    def test_load_use_case_file_not_found(self, config_manager):
        """Test loading non-existent use case raises FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="Use case file not found"):
            config_manager.load_use_case("nonexistent")
    
    def test_load_use_case_empty_name(self, config_manager):
        """Test loading with empty name raises ValueError"""
        with pytest.raises(ValueError, match="Use case name cannot be empty"):
            config_manager.load_use_case("")
    
    def test_load_use_case_whitespace_name(self, config_manager):
        """Test loading with whitespace-only name raises ValueError"""
        with pytest.raises(ValueError, match="Use case name cannot be empty"):
            config_manager.load_use_case("   ")
    
    def test_load_use_case_missing_required_field(self, config_manager, create_use_case_file):
        """Test loading use case with missing required field"""
        incomplete_yaml = """
name: incomplete
description: Missing test_questions field
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
"""
        create_use_case_file("incomplete", incomplete_yaml)
        
        with pytest.raises(KeyError, match="Missing required field"):
            config_manager.load_use_case("incomplete")
    
    def test_load_use_case_invalid_yaml(self, config_manager, create_use_case_file):
        """Test loading malformed YAML raises YAMLError"""
        invalid_yaml = """
name: invalid
description: [unclosed bracket
"""
        create_use_case_file("invalid", invalid_yaml)
        
        with pytest.raises(yaml.YAMLError, match="Failed to parse YAML"):
            config_manager.load_use_case("invalid")
    
    def test_load_use_case_not_dict(self, config_manager, create_use_case_file):
        """Test loading YAML that's not a dictionary"""
        list_yaml = """
- item1
- item2
"""
        create_use_case_file("list_yaml", list_yaml)
        
        with pytest.raises(TypeError, match="YAML file must contain a dictionary"):
            config_manager.load_use_case("list_yaml")
    
    def test_load_use_case_invalid_test_questions_type(self, config_manager, create_use_case_file):
        """Test loading use case with test_questions as string instead of list"""
        invalid_yaml = """
name: invalid_questions
description: Test description
test_questions: "This should be a list"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
"""
        create_use_case_file("invalid_questions", invalid_yaml)
        
        with pytest.raises(TypeError, match="test_questions must be a list"):
            config_manager.load_use_case("invalid_questions")
    
    def test_load_use_case_empty_test_questions(self, config_manager, create_use_case_file):
        """Test loading use case with empty test_questions list"""
        empty_questions_yaml = """
name: empty_questions
description: Test description
test_questions: []
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
"""
        create_use_case_file("empty_questions", empty_questions_yaml)
        
        with pytest.raises(ValueError, match="must have at least one test question"):
            config_manager.load_use_case("empty_questions")
    
    def test_load_use_case_default_version(self, config_manager, create_use_case_file):
        """Test loading use case without version field uses default"""
        no_version_yaml = """
name: no_version
description: Test description
test_questions:
  - "Question 1"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
"""
        create_use_case_file("no_version", no_version_yaml)
        
        use_case = config_manager.load_use_case("no_version")
        
        assert use_case.version == 1
    
    def test_load_use_case_default_created_at(self, config_manager, create_use_case_file):
        """Test loading use case without created_at field uses current time"""
        no_created_at_yaml = """
name: no_created_at
description: Test description
test_questions:
  - "Question 1"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
"""
        create_use_case_file("no_created_at", no_created_at_yaml)
        
        before = datetime.now()
        use_case = config_manager.load_use_case("no_created_at")
        after = datetime.now()
        
        assert before <= use_case.created_at <= after
    
    def test_load_use_case_parses_iso_datetime(self, config_manager, create_use_case_file):
        """Test loading use case with ISO format datetime string"""
        iso_datetime_yaml = """
name: iso_datetime
description: Test description
test_questions:
  - "Question 1"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
created_at: 2024-01-15T10:30:00Z
"""
        create_use_case_file("iso_datetime", iso_datetime_yaml)
        
        use_case = config_manager.load_use_case("iso_datetime")
        
        # Check that datetime was parsed (exact comparison may vary due to timezone)
        assert use_case.created_at.year == 2024
        assert use_case.created_at.month == 1
        assert use_case.created_at.day == 15
    
    def test_load_use_case_invalid_datetime_uses_default(self, config_manager, create_use_case_file):
        """Test loading use case with invalid datetime string uses current time"""
        invalid_datetime_yaml = """
name: invalid_datetime
description: Test description
test_questions:
  - "Question 1"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
created_at: "not a valid datetime"
"""
        create_use_case_file("invalid_datetime", invalid_datetime_yaml)
        
        before = datetime.now()
        use_case = config_manager.load_use_case("invalid_datetime")
        after = datetime.now()
        
        assert before <= use_case.created_at <= after
    
    def test_load_use_case_with_multiline_strings(self, config_manager, create_use_case_file):
        """Test loading use case with multiline YAML strings"""
        multiline_yaml = """
name: multiline
description: |
  This is a multiline description.
  It spans multiple lines.
  And preserves formatting.
test_questions:
  - "Question 1"
judge_criteria: |
  Criterion 1
  Criterion 2
data_generation_prompt: |
  Line 1
  Line 2
judge_prompt: |
  Judge instruction 1
  Judge instruction 2
"""
        create_use_case_file("multiline", multiline_yaml)
        
        use_case = config_manager.load_use_case("multiline")
        
        assert "multiline description" in use_case.description
        assert "\n" in use_case.description
        assert "Criterion 1" in use_case.judge_criteria
        assert "Line 1" in use_case.data_generation_prompt
    
    def test_load_use_case_with_special_characters(self, config_manager, create_use_case_file):
        """Test loading use case with special characters in strings"""
        special_chars_yaml = """
name: special_chars
description: "Description with 'quotes' and \\"double quotes\\""
test_questions:
  - "What's the answer?"
  - "How do I use @mentions?"
  - "What about #hashtags?"
judge_criteria: "Criteria with $pecial ch@rs!"
data_generation_prompt: "Prompt with émojis 🎉"
judge_prompt: "Judge with symbols: & | < >"
"""
        create_use_case_file("special_chars", special_chars_yaml)
        
        use_case = config_manager.load_use_case("special_chars")
        
        assert "quotes" in use_case.description
        assert "@mentions" in use_case.test_questions[1]
        assert "$pecial" in use_case.judge_criteria
    
    def test_load_use_case_multiple_questions(self, config_manager, create_use_case_file):
        """Test loading use case with many test questions"""
        many_questions_yaml = """
name: many_questions
description: Test with many questions
test_questions:
  - "Question 1"
  - "Question 2"
  - "Question 3"
  - "Question 4"
  - "Question 5"
  - "Question 6"
  - "Question 7"
  - "Question 8"
  - "Question 9"
  - "Question 10"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
"""
        create_use_case_file("many_questions", many_questions_yaml)
        
        use_case = config_manager.load_use_case("many_questions")
        
        assert len(use_case.test_questions) == 10
        assert use_case.test_questions[0] == "Question 1"
        assert use_case.test_questions[9] == "Question 10"
    
    def test_load_use_case_strips_name_whitespace(self, config_manager, create_use_case_file):
        """Test that load_use_case strips whitespace from name"""
        create_use_case_file("test_case")
        
        use_case = config_manager.load_use_case("  test_case  ")
        
        assert use_case.name == "test_use_case"
    
    def test_load_use_case_logs_info(self, config_manager, create_use_case_file, caplog):
        """Test that load_use_case logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        create_use_case_file("test_case")
        
        use_case = config_manager.load_use_case("test_case")
        
        assert "Loading use case 'test_case'" in caplog.text
        assert "Successfully loaded use case" in caplog.text
    
    def test_load_use_case_error_includes_available_cases(self, config_manager, create_use_case_file):
        """Test that FileNotFoundError includes list of available use cases"""
        create_use_case_file("available_case")
        
        with pytest.raises(FileNotFoundError, match="available_case"):
            config_manager.load_use_case("nonexistent")
    
    def test_load_use_case_validates_empty_fields(self, config_manager, create_use_case_file):
        """Test that empty required fields are rejected"""
        empty_field_yaml = """
name: ""
description: Test description
test_questions:
  - "Question 1"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
"""
        create_use_case_file("empty_field", empty_field_yaml)
        
        with pytest.raises(ValueError, match="name cannot be empty"):
            config_manager.load_use_case("empty_field")
    
    def test_load_use_case_higher_version(self, config_manager, create_use_case_file):
        """Test loading use case with version > 1"""
        versioned_yaml = """
name: versioned
description: Test description
test_questions:
  - "Question 1"
judge_criteria: Some criteria
data_generation_prompt: Some prompt
judge_prompt: Some judge prompt
version: 5
"""
        create_use_case_file("versioned", versioned_yaml)
        
        use_case = config_manager.load_use_case("versioned")
        
        assert use_case.version == 5
    
    def test_load_use_case_unicode_content(self, config_manager, create_use_case_file):
        """Test loading use case with Unicode characters"""
        unicode_yaml = """
name: unicode_test
description: "Description with Unicode: 你好, مرحبا, Привет"
test_questions:
  - "Question with émojis: 🎉 🚀 ✨"
  - "Question with accents: café, naïve, résumé"
judge_criteria: "Criteria with symbols: ≈ ≠ ≤ ≥"
data_generation_prompt: "Prompt with currency: € £ ¥ ₹"
judge_prompt: "Judge with math: α β γ δ"
"""
        create_use_case_file("unicode_test", unicode_yaml)
        
        use_case = config_manager.load_use_case("unicode_test")
        
        assert "你好" in use_case.description
        assert "🎉" in use_case.test_questions[0]
        assert "café" in use_case.test_questions[1]


class TestConfigurationManagerListUseCases:
    """Test suite for ConfigurationManager.list_use_cases()"""
    
    def test_list_use_cases_empty_directory(self, config_manager):
        """Test listing use cases in empty directory"""
        use_cases = config_manager.list_use_cases()
        
        assert use_cases == []
    
    def test_list_use_cases_single_file(self, config_manager, create_use_case_file):
        """Test listing single use case"""
        create_use_case_file("test_case")
        
        use_cases = config_manager.list_use_cases()
        
        assert use_cases == ["test_case"]
    
    def test_list_use_cases_multiple_files(self, config_manager, create_use_case_file):
        """Test listing multiple use cases"""
        create_use_case_file("case_a")
        create_use_case_file("case_b")
        create_use_case_file("case_c")
        
        use_cases = config_manager.list_use_cases()
        
        assert len(use_cases) == 3
        assert "case_a" in use_cases
        assert "case_b" in use_cases
        assert "case_c" in use_cases
    
    def test_list_use_cases_sorted_alphabetically(self, config_manager, create_use_case_file):
        """Test that use cases are sorted alphabetically"""
        create_use_case_file("zebra")
        create_use_case_file("apple")
        create_use_case_file("mango")
        
        use_cases = config_manager.list_use_cases()
        
        assert use_cases == ["apple", "mango", "zebra"]
    
    def test_list_use_cases_ignores_non_yaml_files(self, config_manager, temp_config_dir):
        """Test that non-YAML files are ignored"""
        use_cases_dir = temp_config_dir / "use_cases"
        use_cases_dir.mkdir(parents=True, exist_ok=True)
        
        # Create YAML file
        (use_cases_dir / "valid.yaml").write_text("name: valid")
        
        # Create non-YAML files
        (use_cases_dir / "readme.txt").write_text("readme")
        (use_cases_dir / "config.json").write_text("{}")
        
        use_cases = config_manager.list_use_cases()
        
        assert use_cases == ["valid"]
    
    def test_list_use_cases_removes_yaml_extension(self, config_manager, create_use_case_file):
        """Test that .yaml extension is removed from names"""
        create_use_case_file("test_case")
        
        use_cases = config_manager.list_use_cases()
        
        assert "test_case" in use_cases
        assert "test_case.yaml" not in use_cases
    
    def test_list_use_cases_ignores_backup_files(self, config_manager, temp_config_dir):
        """Test that versioned backup files are excluded from listing"""
        use_cases_dir = temp_config_dir / "use_cases"
        use_cases_dir.mkdir(parents=True, exist_ok=True)
        
        # Create main use case file
        (use_cases_dir / "customer_support.yaml").write_text("name: customer_support")
        
        # Create backup files (should be ignored)
        (use_cases_dir / "customer_support.v1.20240115_103000.yaml").write_text("name: customer_support")
        (use_cases_dir / "customer_support.v2.20240116_143000.yaml").write_text("name: customer_support")
        
        use_cases = config_manager.list_use_cases()
        
        # Should only return the main file, not backups
        assert use_cases == ["customer_support"]
    
    def test_list_use_cases_multiple_with_backups(self, config_manager, temp_config_dir):
        """Test listing multiple use cases with backup files present"""
        use_cases_dir = temp_config_dir / "use_cases"
        use_cases_dir.mkdir(parents=True, exist_ok=True)
        
        # Create main files
        (use_cases_dir / "case_a.yaml").write_text("name: case_a")
        (use_cases_dir / "case_b.yaml").write_text("name: case_b")
        
        # Create backup files
        (use_cases_dir / "case_a.v1.20240115_103000.yaml").write_text("name: case_a")
        (use_cases_dir / "case_b.v1.20240115_103000.yaml").write_text("name: case_b")
        (use_cases_dir / "case_b.v2.20240116_143000.yaml").write_text("name: case_b")
        
        use_cases = config_manager.list_use_cases()
        
        assert use_cases == ["case_a", "case_b"]


class TestConfigurationManagerSaveUseCase:
    """Test suite for ConfigurationManager.save_use_case()"""
    
    def test_save_use_case_new(self, config_manager):
        """Test saving a new use case"""
        use_case = UseCase(
            name="new_case",
            description="A new test case",
            test_questions=["Question 1", "Question 2"],
            judge_criteria="Test criteria",
            data_generation_prompt="Generate data",
            judge_prompt="Judge responses",
            version=1
        )
        
        config_manager.save_use_case(use_case)
        
        # Verify file was created
        use_case_path = config_manager.use_cases_dir / "new_case.yaml"
        assert use_case_path.exists()
        
        # Verify content by loading it back
        loaded = config_manager.load_use_case("new_case")
        assert loaded.name == "new_case"
        assert loaded.description == "A new test case"
        assert len(loaded.test_questions) == 2
        assert loaded.version == 1
    
    def test_save_use_case_update_increments_version(self, config_manager):
        """Test that updating a use case increments version"""
        # Create initial use case
        use_case_v1 = UseCase(
            name="update_test",
            description="Version 1",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge",
            version=1
        )
        config_manager.save_use_case(use_case_v1)
        
        # Update use case
        use_case_v2 = UseCase(
            name="update_test",
            description="Version 2",
            test_questions=["Q1", "Q2"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge",
            version=1  # Will be incremented automatically
        )
        config_manager.save_use_case(use_case_v2)
        
        # Verify version was incremented
        loaded = config_manager.load_use_case("update_test")
        assert loaded.version == 2
        assert loaded.description == "Version 2"
        assert len(loaded.test_questions) == 2
    
    def test_save_use_case_creates_backup(self, config_manager):
        """Test that updating creates a backup of previous version"""
        # Create initial use case
        use_case_v1 = UseCase(
            name="backup_test",
            description="Version 1",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge",
            version=1
        )
        config_manager.save_use_case(use_case_v1)
        
        # Update use case
        use_case_v2 = UseCase(
            name="backup_test",
            description="Version 2",
            test_questions=["Q1", "Q2"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge",
            version=1
        )
        config_manager.save_use_case(use_case_v2)
        
        # Verify backup file was created
        backup_files = list(config_manager.use_cases_dir.glob("backup_test.v1.*.yaml"))
        assert len(backup_files) == 1
        
        # Verify backup contains old version
        with open(backup_files[0], 'r') as f:
            backup_data = yaml.safe_load(f)
        assert backup_data['description'] == "Version 1"
        assert backup_data['version'] == 1
    
    def test_save_use_case_multiple_updates(self, config_manager):
        """Test multiple updates create multiple backups with incrementing versions"""
        use_case = UseCase(
            name="multi_update",
            description="Version 1",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge",
            version=1
        )
        
        # Save version 1
        config_manager.save_use_case(use_case)
        
        # Update to version 2
        use_case.description = "Version 2"
        config_manager.save_use_case(use_case)
        
        # Update to version 3
        use_case.description = "Version 3"
        config_manager.save_use_case(use_case)
        
        # Verify current version
        loaded = config_manager.load_use_case("multi_update")
        assert loaded.version == 3
        assert loaded.description == "Version 3"
        
        # Verify backups exist
        backup_v1 = list(config_manager.use_cases_dir.glob("multi_update.v1.*.yaml"))
        backup_v2 = list(config_manager.use_cases_dir.glob("multi_update.v2.*.yaml"))
        assert len(backup_v1) == 1
        assert len(backup_v2) == 1
    
    def test_save_use_case_preserves_all_fields(self, config_manager):
        """Test that all use case fields are preserved in saved file"""
        created_time = datetime(2024, 1, 15, 10, 30, 0)
        use_case = UseCase(
            name="complete_case",
            description="Complete description",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Detailed criteria",
            data_generation_prompt="Detailed prompt",
            judge_prompt="Detailed judge prompt",
            version=5,
            created_at=created_time
        )
        
        config_manager.save_use_case(use_case)
        
        # Load and verify all fields
        loaded = config_manager.load_use_case("complete_case")
        assert loaded.name == "complete_case"
        assert loaded.description == "Complete description"
        assert loaded.test_questions == ["Q1", "Q2", "Q3"]
        assert loaded.judge_criteria == "Detailed criteria"
        assert loaded.data_generation_prompt == "Detailed prompt"
        assert loaded.judge_prompt == "Detailed judge prompt"
        assert loaded.version == 5
        assert loaded.created_at.year == 2024
        assert loaded.created_at.month == 1
        assert loaded.created_at.day == 15
    
    def test_save_use_case_with_multiline_strings(self, config_manager):
        """Test saving use case with multiline strings"""
        use_case = UseCase(
            name="multiline_case",
            description="Line 1\nLine 2\nLine 3",
            test_questions=["Question 1"],
            judge_criteria="Criteria line 1\nCriteria line 2",
            data_generation_prompt="Prompt line 1\nPrompt line 2",
            judge_prompt="Judge line 1\nJudge line 2"
        )
        
        config_manager.save_use_case(use_case)
        
        # Verify multiline strings are preserved
        loaded = config_manager.load_use_case("multiline_case")
        assert "\n" in loaded.description
        assert "Line 1" in loaded.description
        assert "Line 3" in loaded.description
    
    def test_save_use_case_with_special_characters(self, config_manager):
        """Test saving use case with special characters"""
        use_case = UseCase(
            name="special_chars",
            description="Description with 'quotes' and \"double quotes\"",
            test_questions=["What's the answer?", "How about @mentions?"],
            judge_criteria="Criteria with $pecial ch@rs!",
            data_generation_prompt="Prompt with émojis 🎉",
            judge_prompt="Judge with symbols: & | < >"
        )
        
        config_manager.save_use_case(use_case)
        
        # Verify special characters are preserved
        loaded = config_manager.load_use_case("special_chars")
        assert "quotes" in loaded.description
        assert "@mentions" in loaded.test_questions[1]
        assert "$pecial" in loaded.judge_criteria
    
    def test_save_use_case_with_unicode(self, config_manager):
        """Test saving use case with Unicode characters"""
        use_case = UseCase(
            name="unicode_case",
            description="Unicode: 你好, مرحبا, Привет",
            test_questions=["Question with émojis: 🎉 🚀"],
            judge_criteria="Criteria with symbols: ≈ ≠ ≤",
            data_generation_prompt="Prompt with currency: € £ ¥",
            judge_prompt="Judge with math: α β γ"
        )
        
        config_manager.save_use_case(use_case)
        
        # Verify Unicode is preserved
        loaded = config_manager.load_use_case("unicode_case")
        assert "你好" in loaded.description
        assert "🎉" in loaded.test_questions[0]
        assert "€" in loaded.data_generation_prompt
    
    def test_save_use_case_none_raises_error(self, config_manager):
        """Test that saving None raises ValueError"""
        with pytest.raises(ValueError, match="use_case cannot be None"):
            config_manager.save_use_case(None)
    
    def test_save_use_case_invalid_use_case_raises_error(self, config_manager):
        """Test that saving invalid use case raises error"""
        # Create use case with empty name (should fail validation)
        with pytest.raises(ValueError):
            use_case = UseCase(
                name="",
                description="Description",
                test_questions=["Q1"],
                judge_criteria="Criteria",
                data_generation_prompt="Prompt",
                judge_prompt="Judge"
            )
    
    def test_save_use_case_creates_directory_if_missing(self, temp_config_dir):
        """Test that save creates use_cases directory if it doesn't exist"""
        # Remove use_cases directory
        use_cases_dir = temp_config_dir / "use_cases"
        if use_cases_dir.exists():
            import shutil
            shutil.rmtree(use_cases_dir)
        
        # Create config manager (should recreate directory)
        config_manager = ConfigurationManager(str(temp_config_dir))
        
        use_case = UseCase(
            name="test_case",
            description="Test",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        config_manager.save_use_case(use_case)
        
        # Verify file was created
        assert (use_cases_dir / "test_case.yaml").exists()
    
    def test_save_use_case_atomic_write(self, config_manager):
        """Test that save uses atomic write (temp file then rename)"""
        use_case = UseCase(
            name="atomic_test",
            description="Test atomic write",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        config_manager.save_use_case(use_case)
        
        # Verify no temp files left behind
        temp_files = list(config_manager.use_cases_dir.glob("*.tmp"))
        assert len(temp_files) == 0
        
        # Verify main file exists
        assert (config_manager.use_cases_dir / "atomic_test.yaml").exists()
    
    def test_save_use_case_logs_info(self, config_manager, caplog):
        """Test that save_use_case logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        use_case = UseCase(
            name="log_test",
            description="Test logging",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        config_manager.save_use_case(use_case)
        
        assert "Saving use case 'log_test'" in caplog.text
        assert "Successfully saved use case" in caplog.text
    
    def test_save_use_case_round_trip(self, config_manager):
        """Test that saving and loading preserves all data (round-trip)"""
        original = UseCase(
            name="round_trip",
            description="Test round trip",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge",
            version=1,
            created_at=datetime(2024, 1, 15, 10, 30, 0)
        )
        
        config_manager.save_use_case(original)
        loaded = config_manager.load_use_case("round_trip")
        
        # Verify all fields match
        assert loaded.name == original.name
        assert loaded.description == original.description
        assert loaded.test_questions == original.test_questions
        assert loaded.judge_criteria == original.judge_criteria
        assert loaded.data_generation_prompt == original.data_generation_prompt
        assert loaded.judge_prompt == original.judge_prompt
        assert loaded.version == original.version
        # Compare datetime (may have slight differences due to serialization)
        assert loaded.created_at.year == original.created_at.year
        assert loaded.created_at.month == original.created_at.month
        assert loaded.created_at.day == original.created_at.day
    
    def test_save_use_case_backup_timestamp_format(self, config_manager):
        """Test that backup files have correct timestamp format"""
        use_case = UseCase(
            name="timestamp_test",
            description="Version 1",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        # Save twice to create backup
        config_manager.save_use_case(use_case)
        use_case.description = "Version 2"
        config_manager.save_use_case(use_case)
        
        # Find backup file
        backup_files = list(config_manager.use_cases_dir.glob("timestamp_test.v1.*.yaml"))
        assert len(backup_files) == 1
        
        # Verify filename format: name.v{version}.{timestamp}.yaml
        backup_name = backup_files[0].stem
        parts = backup_name.split('.')
        assert len(parts) >= 3
        assert parts[1] == "v1"
        # Timestamp should be in format YYYYMMDD_HHMMSS
        assert len(parts[2]) == 15  # YYYYMMDD_HHMMSS
        assert '_' in parts[2]
    
    def test_save_use_case_handles_write_error_gracefully(self, config_manager, temp_config_dir):
        """Test that write errors are handled gracefully"""
        use_case = UseCase(
            name="write_error_test",
            description="Test",
            test_questions=["Q1"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        # Make directory read-only (Unix-like systems)
        if os.name != 'nt':  # Skip on Windows
            use_cases_dir = temp_config_dir / "use_cases"
            os.chmod(use_cases_dir, 0o444)
            
            try:
                with pytest.raises(OSError, match="Failed to write use case file"):
                    config_manager.save_use_case(use_case)
            finally:
                # Restore permissions for cleanup
                os.chmod(use_cases_dir, 0o755)
    
    def test_save_use_case_yaml_format(self, config_manager):
        """Test that saved YAML has correct format"""
        use_case = UseCase(
            name="yaml_format_test",
            description="Test YAML format",
            test_questions=["Q1", "Q2"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        config_manager.save_use_case(use_case)
        
        # Read raw YAML file
        yaml_path = config_manager.use_cases_dir / "yaml_format_test.yaml"
        with open(yaml_path, 'r') as f:
            content = f.read()
        
        # Verify YAML structure
        assert "name: yaml_format_test" in content
        assert "description:" in content
        assert "test_questions:" in content
        assert "- Q1" in content or "- 'Q1'" in content
        assert "judge_criteria:" in content
        assert "version:" in content
        assert "created_at:" in content



class TestConfigurationManagerLoadPipelineConfig:
    """Test suite for ConfigurationManager.load_pipeline_config()"""
    
    @pytest.fixture
    def sample_pipeline_config_yaml(self):
        """Fixture providing sample pipeline configuration YAML"""
        return """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-finetuning-bucket

training:
  base_model: meta-llama/Llama-3.2-3B
  instance_type: ml.g5.xlarge
  max_training_time_seconds: 3600

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
  artifact_retention_days: 7

retry:
  max_attempts: 3
  initial_backoff_seconds: 2
  max_backoff_seconds: 60
"""
    
    @pytest.fixture
    def create_pipeline_config_file(self, temp_config_dir):
        """Fixture that creates a pipeline config YAML file"""
        def _create_file(name="pipeline_config", content=None):
            file_path = temp_config_dir / f"{name}.yaml"
            file_path.write_text(content, encoding='utf-8')
            return file_path
        return _create_file
    
    def test_load_pipeline_config_default(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml):
        """Test loading default pipeline configuration"""
        create_pipeline_config_file("pipeline_config", sample_pipeline_config_yaml)
        
        config = config_manager.load_pipeline_config()
        
        assert config.aws_region == "us-east-1"
        assert config.bedrock_model_id == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert config.sagemaker_role_arn == "arn:aws:iam::123456789012:role/SageMakerRole"
        assert config.s3_bucket == "test-finetuning-bucket"
        assert config.training_instance_type == "ml.g5.xlarge"
        assert config.inference_instance_type == "ml.g5.xlarge"
        assert config.baseline_model_endpoint == "llama-70b-baseline"
        assert config.performance_threshold == 0.60
        assert config.max_iterations == 3
        assert config.cleanup_resources is True
        assert config.artifact_retention_days == 7
        assert config.max_retries == 3
        assert config.initial_backoff_seconds == 2
        assert config.max_backoff_seconds == 60
    
    def test_load_pipeline_config_with_name(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml):
        """Test loading pipeline configuration with specific name"""
        create_pipeline_config_file("pipeline_config", sample_pipeline_config_yaml)
        
        config = config_manager.load_pipeline_config("pipeline_config")
        
        assert config.aws_region == "us-east-1"
        assert config.performance_threshold == 0.60
    
    def test_load_pipeline_config_environment_specific_dev(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml):
        """Test loading environment-specific configuration (dev)"""
        create_pipeline_config_file("pipeline_config.dev", sample_pipeline_config_yaml)
        
        config = config_manager.load_pipeline_config("dev")
        
        assert config.aws_region == "us-east-1"
    
    def test_load_pipeline_config_environment_specific_prod(self, config_manager, create_pipeline_config_file):
        """Test loading environment-specific configuration (prod)"""
        prod_config = """
aws:
  region: us-west-2
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerProdRole
  s3_bucket: prod-finetuning-bucket

training:
  instance_type: ml.g5.2xlarge
  max_training_time_seconds: 21600

inference:
  instance_type: ml.g5.2xlarge
  baseline_model_endpoint: llama-70b-baseline-prod

pipeline:
  performance_threshold: 0.70
  max_iterations: 5
  cleanup_resources: false
  artifact_retention_days: 30

retry:
  max_attempts: 5
  initial_backoff_seconds: 2
  max_backoff_seconds: 60
"""
        create_pipeline_config_file("pipeline_config.prod", prod_config)
        
        config = config_manager.load_pipeline_config("prod")
        
        assert config.aws_region == "us-west-2"
        assert config.training_instance_type == "ml.g5.2xlarge"
        assert config.performance_threshold == 0.70
        assert config.max_iterations == 5
        assert config.cleanup_resources is False
        assert config.artifact_retention_days == 30
    
    def test_load_pipeline_config_with_yaml_extension(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml):
        """Test loading configuration with .yaml extension in name"""
        create_pipeline_config_file("pipeline_config", sample_pipeline_config_yaml)
        
        config = config_manager.load_pipeline_config("pipeline_config.yaml")
        
        assert config.aws_region == "us-east-1"
    
    def test_load_pipeline_config_fallback_to_default(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml):
        """Test that loading non-existent config falls back to default"""
        create_pipeline_config_file("pipeline_config", sample_pipeline_config_yaml)
        
        # Request "custom" but only "pipeline_config" exists
        config = config_manager.load_pipeline_config("custom")
        
        # Should fall back to pipeline_config.yaml
        assert config.aws_region == "us-east-1"
    
    def test_load_pipeline_config_file_not_found(self, config_manager):
        """Test loading non-existent configuration raises FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="Pipeline configuration file not found"):
            config_manager.load_pipeline_config("nonexistent")
    
    def test_load_pipeline_config_empty_name(self, config_manager):
        """Test loading with empty name raises ValueError"""
        with pytest.raises(ValueError, match="config_name cannot be empty"):
            config_manager.load_pipeline_config("")
    
    def test_load_pipeline_config_whitespace_name(self, config_manager):
        """Test loading with whitespace-only name raises ValueError"""
        with pytest.raises(ValueError, match="config_name cannot be empty"):
            config_manager.load_pipeline_config("   ")
    
    def test_load_pipeline_config_missing_aws_section(self, config_manager, create_pipeline_config_file):
        """Test loading config without aws section raises KeyError"""
        incomplete_config = """
training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", incomplete_config)
        
        with pytest.raises(KeyError, match="aws.*section is required"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_missing_training_section(self, config_manager, create_pipeline_config_file):
        """Test loading config without training section raises KeyError"""
        incomplete_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", incomplete_config)
        
        with pytest.raises(KeyError, match="training.*section is required"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_missing_inference_section(self, config_manager, create_pipeline_config_file):
        """Test loading config without inference section raises KeyError"""
        incomplete_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", incomplete_config)
        
        with pytest.raises(KeyError, match="inference.*section is required"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_missing_pipeline_section(self, config_manager, create_pipeline_config_file):
        """Test loading config without pipeline section raises KeyError"""
        incomplete_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline
"""
        create_pipeline_config_file("pipeline_config", incomplete_config)
        
        with pytest.raises(KeyError, match="pipeline.*section is required"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_missing_required_aws_field(self, config_manager, create_pipeline_config_file):
        """Test loading config with missing required AWS field"""
        incomplete_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  # Missing sagemaker_role_arn
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", incomplete_config)
        
        with pytest.raises(KeyError, match="aws.sagemaker_role_arn.*is required"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_missing_required_pipeline_field(self, config_manager, create_pipeline_config_file):
        """Test loading config with missing required pipeline field"""
        incomplete_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  # Missing max_iterations
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", incomplete_config)
        
        with pytest.raises(KeyError, match="pipeline.max_iterations.*is required"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_invalid_yaml(self, config_manager, create_pipeline_config_file):
        """Test loading malformed YAML raises YAMLError"""
        invalid_yaml = """
aws:
  region: us-east-1
  bedrock_model_id: [unclosed bracket
"""
        create_pipeline_config_file("pipeline_config", invalid_yaml)
        
        with pytest.raises(yaml.YAMLError, match="Failed to parse YAML"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_not_dict(self, config_manager, create_pipeline_config_file):
        """Test loading YAML that's not a dictionary"""
        list_yaml = """
- item1
- item2
"""
        create_pipeline_config_file("pipeline_config", list_yaml)
        
        with pytest.raises(TypeError, match="YAML file must contain a dictionary"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_default_values(self, config_manager, create_pipeline_config_file):
        """Test that optional fields use default values"""
        minimal_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge
  # base_model and max_training_time_seconds omitted

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
  # artifact_retention_days omitted

# retry section omitted entirely
"""
        create_pipeline_config_file("pipeline_config", minimal_config)
        
        config = config_manager.load_pipeline_config()
        
        # Verify defaults are applied
        assert config.base_model == "meta-llama/Llama-3.2-3B"
        assert config.max_training_time_seconds == 86400
        assert config.artifact_retention_days == 7
        assert config.max_retries == 3
        assert config.initial_backoff_seconds == 2
        assert config.max_backoff_seconds == 60
    
    def test_load_pipeline_config_custom_retry_values(self, config_manager, create_pipeline_config_file):
        """Test loading config with custom retry values"""
        config_with_retry = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true

retry:
  max_attempts: 5
  initial_backoff_seconds: 5
  max_backoff_seconds: 120
"""
        create_pipeline_config_file("pipeline_config", config_with_retry)
        
        config = config_manager.load_pipeline_config()
        
        assert config.max_retries == 5
        assert config.initial_backoff_seconds == 5
        assert config.max_backoff_seconds == 120
    
    def test_load_pipeline_config_invalid_threshold(self, config_manager, create_pipeline_config_file):
        """Test loading config with invalid performance threshold"""
        invalid_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 1.5  # Invalid: > 1.0
  max_iterations: 3
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", invalid_config)
        
        with pytest.raises(ValueError, match="Performance threshold must be between 0.0 and 1.0"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_invalid_max_iterations(self, config_manager, create_pipeline_config_file):
        """Test loading config with invalid max_iterations"""
        invalid_config = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 0  # Invalid: must be >= 1
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", invalid_config)
        
        with pytest.raises(ValueError, match="Max iterations must be >= 1"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_type_conversion(self, config_manager, create_pipeline_config_file):
        """Test that numeric values are properly converted to correct types"""
        config_yaml = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge
  max_training_time_seconds: "7200"  # String that should be converted to int

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: "0.75"  # String that should be converted to float
  max_iterations: "5"  # String that should be converted to int
  cleanup_resources: true

retry:
  max_attempts: "4"  # String that should be converted to int
"""
        create_pipeline_config_file("pipeline_config", config_yaml)
        
        config = config_manager.load_pipeline_config()
        
        # Verify types are correct
        assert isinstance(config.max_training_time_seconds, int)
        assert config.max_training_time_seconds == 7200
        assert isinstance(config.performance_threshold, float)
        assert config.performance_threshold == 0.75
        assert isinstance(config.max_iterations, int)
        assert config.max_iterations == 5
        assert isinstance(config.max_retries, int)
        assert config.max_retries == 4
    
    def test_load_pipeline_config_boolean_conversion(self, config_manager, create_pipeline_config_file):
        """Test that boolean values are properly converted"""
        config_yaml = """
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: false  # Boolean false
"""
        create_pipeline_config_file("pipeline_config", config_yaml)
        
        config = config_manager.load_pipeline_config()
        
        assert isinstance(config.cleanup_resources, bool)
        assert config.cleanup_resources is False
    
    def test_load_pipeline_config_strips_name_whitespace(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml):
        """Test that config_name whitespace is stripped"""
        create_pipeline_config_file("pipeline_config", sample_pipeline_config_yaml)
        
        config = config_manager.load_pipeline_config("  pipeline_config  ")
        
        assert config.aws_region == "us-east-1"
    
    def test_load_pipeline_config_logs_info(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml, caplog):
        """Test that load_pipeline_config logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        create_pipeline_config_file("pipeline_config", sample_pipeline_config_yaml)
        
        config = config_manager.load_pipeline_config()
        
        assert "Loading pipeline configuration" in caplog.text
        assert "Successfully loaded pipeline configuration" in caplog.text
    
    def test_load_pipeline_config_error_message_includes_searched_paths(self, config_manager):
        """Test that FileNotFoundError includes list of searched paths"""
        with pytest.raises(FileNotFoundError) as exc_info:
            config_manager.load_pipeline_config("missing")
        
        error_msg = str(exc_info.value)
        assert "Searched for:" in error_msg
        assert "missing.yaml" in error_msg
        assert "pipeline_config.missing.yaml" in error_msg
        assert "pipeline_config.yaml" in error_msg
    
    def test_load_pipeline_config_validates_empty_required_fields(self, config_manager, create_pipeline_config_file):
        """Test that empty required fields are rejected"""
        invalid_config = """
aws:
  region: ""  # Empty string
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: test-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
"""
        create_pipeline_config_file("pipeline_config", invalid_config)
        
        with pytest.raises(KeyError, match="aws.region.*is required"):
            config_manager.load_pipeline_config()
    
    def test_load_pipeline_config_all_fields_populated(self, config_manager, create_pipeline_config_file):
        """Test that all PipelineConfig fields are populated"""
        complete_config = """
aws:
  region: us-west-2
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: complete-test-bucket

training:
  base_model: meta-llama/Llama-3.2-3B
  instance_type: ml.g5.2xlarge
  max_training_time_seconds: 10800

inference:
  instance_type: ml.g5.2xlarge
  baseline_model_endpoint: llama-70b-baseline-complete

pipeline:
  performance_threshold: 0.65
  max_iterations: 4
  cleanup_resources: false
  artifact_retention_days: 14

retry:
  max_attempts: 4
  initial_backoff_seconds: 3
  max_backoff_seconds: 90
"""
        create_pipeline_config_file("pipeline_config", complete_config)
        
        config = config_manager.load_pipeline_config()
        
        # Verify all fields are populated
        assert config.aws_region == "us-west-2"
        assert config.bedrock_model_id == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert config.sagemaker_role_arn == "arn:aws:iam::123456789012:role/SageMakerRole"
        assert config.s3_bucket == "complete-test-bucket"
        assert config.base_model == "meta-llama/Llama-3.2-3B"
        assert config.training_instance_type == "ml.g5.2xlarge"
        assert config.max_training_time_seconds == 10800
        assert config.inference_instance_type == "ml.g5.2xlarge"
        assert config.baseline_model_endpoint == "llama-70b-baseline-complete"
        assert config.performance_threshold == 0.65
        assert config.max_iterations == 4
        assert config.cleanup_resources is False
        assert config.artifact_retention_days == 14
        assert config.max_retries == 4
        assert config.initial_backoff_seconds == 3
        assert config.max_backoff_seconds == 90
    
    def test_load_pipeline_config_search_order(self, config_manager, create_pipeline_config_file):
        """Test that configuration files are searched in correct order"""
        # Create multiple config files
        exact_match = """
aws:
  region: exact-match
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: exact-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
"""
        
        env_specific = """
aws:
  region: env-specific
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: env-bucket

training:
  instance_type: ml.g5.xlarge

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 3
  cleanup_resources: true
"""
        
        # Create both files
        create_pipeline_config_file("custom", exact_match)
        create_pipeline_config_file("pipeline_config.custom", env_specific)
        
        # Should prefer exact match (custom.yaml) over environment-specific (pipeline_config.custom.yaml)
        config = config_manager.load_pipeline_config("custom")
        assert config.aws_region == "exact-match"
    
    def test_load_pipeline_config_round_trip_with_save(self, config_manager, create_pipeline_config_file, sample_pipeline_config_yaml):
        """Test that loading a config produces valid PipelineConfig that could be saved"""
        create_pipeline_config_file("pipeline_config", sample_pipeline_config_yaml)
        
        config = config_manager.load_pipeline_config()
        
        # Verify it's a valid PipelineConfig instance
        assert isinstance(config, PipelineConfig)
        
        # Verify all required attributes exist
        assert hasattr(config, 'aws_region')
        assert hasattr(config, 'bedrock_model_id')
        assert hasattr(config, 'sagemaker_role_arn')
        assert hasattr(config, 's3_bucket')
        assert hasattr(config, 'training_instance_type')
        assert hasattr(config, 'inference_instance_type')
        assert hasattr(config, 'baseline_model_endpoint')
        assert hasattr(config, 'performance_threshold')
        assert hasattr(config, 'max_iterations')
        assert hasattr(config, 'cleanup_resources')
