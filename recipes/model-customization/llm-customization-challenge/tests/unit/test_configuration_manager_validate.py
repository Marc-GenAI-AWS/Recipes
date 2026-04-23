"""
Unit Tests for ConfigurationManager.validate_config()

Tests the validate_config() method functionality including:
- UseCase validation (required fields, value ranges, warnings)
- PipelineConfig validation (AWS settings, thresholds, instance types)
- Error and warning detection
- ValidationResult structure
"""

import os
import pytest
from datetime import datetime, timedelta

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.configuration_manager import ConfigurationManager
from src.config_models import UseCase, PipelineConfig, ValidationResult


class TestValidateConfigBasic:
    """Test suite for basic validate_config() functionality"""
    
    def test_validate_config_accepts_use_case(self, tmp_path):
        """Test that validate_config accepts UseCase objects"""
        config_manager = ConfigurationManager(str(tmp_path / "config"))
        
        use_case = UseCase(
            name="test_case",
            description="A valid test case",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Valid criteria",
            data_generation_prompt="Valid prompt",
            judge_prompt="Valid judge prompt"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert isinstance(result, ValidationResult)
    
    def test_validate_config_accepts_pipeline_config(self, tmp_path):
        """Test that validate_config accepts PipelineConfig objects"""
        config_manager = ConfigurationManager(str(tmp_path / "config"))
        
        pipeline_config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(pipeline_config)
        
        assert isinstance(result, ValidationResult)
    
    def test_validate_config_rejects_invalid_type(self, tmp_path):
        """Test that validate_config rejects non-config objects"""
        config_manager = ConfigurationManager(str(tmp_path / "config"))
        
        with pytest.raises(TypeError, match="config must be UseCase or PipelineConfig"):
            config_manager.validate_config("not a config")
        
        with pytest.raises(TypeError, match="config must be UseCase or PipelineConfig"):
            config_manager.validate_config({"name": "dict"})
        
        with pytest.raises(TypeError, match="config must be UseCase or PipelineConfig"):
            config_manager.validate_config(None)


class TestValidateUseCaseRequired:
    """Test suite for UseCase required field validation"""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture providing a ConfigurationManager instance"""
        return ConfigurationManager(str(tmp_path / "config"))
    
    @pytest.fixture
    def valid_use_case(self):
        """Fixture providing a valid UseCase"""
        return UseCase(
            name="valid_case",
            description="A valid test case with sufficient detail",
            test_questions=["Question 1?", "Question 2?", "Question 3?"],
            judge_criteria="Evaluate based on accuracy and helpfulness",
            data_generation_prompt="Generate training examples for customer support",
            judge_prompt="Compare responses and determine which is better"
        )
    
    def test_validate_use_case_valid(self, config_manager, valid_use_case):
        """Test validation of a completely valid use case"""
        result = config_manager.validate_config(valid_use_case)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_use_case_empty_name(self, config_manager):
        """Test that empty name is rejected"""
        # Create use case with empty name (bypassing __post_init__)
        use_case = UseCase.__new__(UseCase)
        use_case.name = ""
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1"]
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("name" in error.lower() and "empty" in error.lower() 
                  for error in result.errors)
    
    def test_validate_use_case_empty_description(self, config_manager):
        """Test that empty description is rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = ""
        use_case.test_questions = ["Q1"]
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("description" in error.lower() and "empty" in error.lower() 
                  for error in result.errors)

    def test_validate_use_case_empty_test_questions(self, config_manager):
        """Test that empty test_questions list is rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = "Valid description"
        use_case.test_questions = []
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("test question" in error.lower() for error in result.errors)
    
    def test_validate_use_case_empty_judge_criteria(self, config_manager):
        """Test that empty judge_criteria is rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1"]
        use_case.judge_criteria = ""
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("judge criteria" in error.lower() and "empty" in error.lower() 
                  for error in result.errors)
    
    def test_validate_use_case_empty_data_generation_prompt(self, config_manager):
        """Test that empty data_generation_prompt is rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1"]
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = ""
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("data generation prompt" in error.lower() and "empty" in error.lower() 
                  for error in result.errors)
    
    def test_validate_use_case_empty_judge_prompt(self, config_manager):
        """Test that empty judge_prompt is rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1"]
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = ""
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("judge prompt" in error.lower() and "empty" in error.lower() 
                  for error in result.errors)


class TestValidateUseCaseWarnings:
    """Test suite for UseCase warning conditions"""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture providing a ConfigurationManager instance"""
        return ConfigurationManager(str(tmp_path / "config"))
    
    def test_validate_use_case_short_name_warning(self, config_manager):
        """Test that short names generate warnings"""
        use_case = UseCase(
            name="ab",  # Only 2 characters
            description="Valid description with enough detail",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True  # Still valid, just a warning
        assert len(result.warnings) > 0
        assert any("name" in warning.lower() and "short" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_use_case_short_description_warning(self, config_manager):
        """Test that short descriptions generate warnings"""
        use_case = UseCase(
            name="test_case",
            description="Short",  # Only 5 characters
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert any("description" in warning.lower() and "short" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_use_case_few_questions_warning(self, config_manager):
        """Test that few test questions generate warnings"""
        use_case = UseCase(
            name="test_case",
            description="Valid description with enough detail",
            test_questions=["Q1", "Q2"],  # Only 2 questions
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert any("question" in warning.lower() and ("2" in warning or "few" in warning.lower()) 
                  for warning in result.warnings)
    
    def test_validate_use_case_many_questions_warning(self, config_manager):
        """Test that many test questions generate warnings"""
        use_case = UseCase(
            name="test_case",
            description="Valid description with enough detail",
            test_questions=[f"Question {i}?" for i in range(60)],  # 60 questions
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert any("question" in warning.lower() and "60" in warning 
                  for warning in result.warnings)

    def test_validate_use_case_duplicate_questions_warning(self, config_manager):
        """Test that duplicate questions generate warnings"""
        use_case = UseCase(
            name="test_case",
            description="Valid description with enough detail",
            test_questions=["Question 1?", "Question 2?", "Question 1?"],  # Duplicate
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert any("duplicate" in warning.lower() for warning in result.warnings)
    
    def test_validate_use_case_long_question_warning(self, config_manager):
        """Test that very long questions generate warnings"""
        long_question = "Q" * 600  # 600 characters
        use_case = UseCase(
            name="test_case",
            description="Valid description with enough detail",
            test_questions=["Q1", "Q2", long_question],
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert any("long" in warning.lower() and "500" in warning 
                  for warning in result.warnings)
    
    def test_validate_use_case_short_prompts_warning(self, config_manager):
        """Test that short prompts generate warnings"""
        use_case = UseCase(
            name="test_case",
            description="Valid description with enough detail",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Short",  # Too short
            data_generation_prompt="Short",  # Too short
            judge_prompt="Short"  # Too short
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert len(result.warnings) >= 3  # One for each short prompt
        assert any("judge criteria" in warning.lower() and "short" in warning.lower() 
                  for warning in result.warnings)
        assert any("data generation prompt" in warning.lower() and "short" in warning.lower() 
                  for warning in result.warnings)
        assert any("judge prompt" in warning.lower() and "short" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_use_case_high_version_warning(self, config_manager):
        """Test that very high version numbers generate warnings"""
        use_case = UseCase(
            name="test_case",
            description="Valid description with enough detail",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail",
            version=1500  # Very high version
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert any("version" in warning.lower() and "high" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_use_case_future_timestamp_warning(self, config_manager):
        """Test that future timestamps generate warnings"""
        future_time = datetime.now() + timedelta(days=1)
        use_case = UseCase(
            name="test_case",
            description="Valid description with enough detail",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Valid criteria with detail",
            data_generation_prompt="Valid prompt with detail",
            judge_prompt="Valid judge prompt with detail",
            created_at=future_time
        )
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is True
        assert any("future" in warning.lower() for warning in result.warnings)


class TestValidateUseCaseEdgeCases:
    """Test suite for UseCase edge cases"""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture providing a ConfigurationManager instance"""
        return ConfigurationManager(str(tmp_path / "config"))
    
    def test_validate_use_case_empty_question_in_list(self, config_manager):
        """Test that empty questions in list are detected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1", "", "Q3"]  # Empty question in middle
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("empty" in error.lower() and "indices" in error.lower() 
                  for error in result.errors)
    
    def test_validate_use_case_long_name_error(self, config_manager):
        """Test that very long names are rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "a" * 150  # 150 characters
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1", "Q2", "Q3"]
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("name" in error.lower() and "long" in error.lower() 
                  for error in result.errors)
    
    def test_validate_use_case_invalid_version(self, config_manager):
        """Test that invalid version numbers are rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1", "Q2", "Q3"]
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 0  # Invalid version
        use_case.created_at = datetime.now()
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("version" in error.lower() for error in result.errors)
    
    def test_validate_use_case_none_created_at(self, config_manager):
        """Test that None created_at is rejected"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = "test"
        use_case.description = "Valid description"
        use_case.test_questions = ["Q1", "Q2", "Q3"]
        use_case.judge_criteria = "Criteria"
        use_case.data_generation_prompt = "Prompt"
        use_case.judge_prompt = "Judge"
        use_case.version = 1
        use_case.created_at = None
        
        result = config_manager.validate_config(use_case)
        
        assert result.is_valid is False
        assert any("created_at" in error.lower() for error in result.errors)


class TestValidatePipelineConfigRequired:
    """Test suite for PipelineConfig required field validation"""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture providing a ConfigurationManager instance"""
        return ConfigurationManager(str(tmp_path / "config"))
    
    @pytest.fixture
    def valid_pipeline_config(self):
        """Fixture providing a valid PipelineConfig"""
        return PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
    
    def test_validate_pipeline_config_valid(self, config_manager, valid_pipeline_config):
        """Test validation of a completely valid pipeline config"""
        result = config_manager.validate_config(valid_pipeline_config)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_pipeline_config_empty_aws_region(self, config_manager):
        """Test that empty AWS region is rejected"""
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = ""
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        config.training_instance_type = "ml.g5.xlarge"
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 0.60
        config.max_iterations = 3
        config.cleanup_resources = True
        config.s3_bucket = "test-bucket"
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("region" in error.lower() and "empty" in error.lower() 
                  for error in result.errors)
    
    def test_validate_pipeline_config_invalid_role_arn(self, config_manager):
        """Test that invalid SageMaker role ARN is rejected"""
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = "us-east-1"
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "invalid-arn"  # Invalid format
        config.training_instance_type = "ml.g5.xlarge"
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 0.60
        config.max_iterations = 3
        config.cleanup_resources = True
        config.s3_bucket = "test-bucket"
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("arn" in error.lower() and "arn:aws:iam::" in error 
                  for error in result.errors)
    
    def test_validate_pipeline_config_invalid_s3_bucket_name(self, config_manager):
        """Test that invalid S3 bucket names are rejected"""
        # Test uppercase (not allowed)
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = "us-east-1"
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        config.training_instance_type = "ml.g5.xlarge"
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 0.60
        config.max_iterations = 3
        config.cleanup_resources = True
        config.s3_bucket = "TestBucket"  # Uppercase not allowed
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("bucket" in error.lower() and "lowercase" in error.lower() 
                  for error in result.errors)
    
    def test_validate_pipeline_config_invalid_instance_type(self, config_manager):
        """Test that invalid instance types are rejected"""
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = "us-east-1"
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        config.training_instance_type = "invalid-instance"  # Missing ml. prefix
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 0.60
        config.max_iterations = 3
        config.cleanup_resources = True
        config.s3_bucket = "test-bucket"
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("instance type" in error.lower() and "ml." in error 
                  for error in result.errors)
    
    def test_validate_pipeline_config_invalid_threshold(self, config_manager):
        """Test that invalid performance thresholds are rejected"""
        # Test threshold > 1.0
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = "us-east-1"
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        config.training_instance_type = "ml.g5.xlarge"
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 1.5  # Invalid: > 1.0
        config.max_iterations = 3
        config.cleanup_resources = True
        config.s3_bucket = "test-bucket"
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("threshold" in error.lower() and "0.0 and 1.0" in error 
                  for error in result.errors)
    
    def test_validate_pipeline_config_invalid_max_iterations(self, config_manager):
        """Test that invalid max_iterations is rejected"""
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = "us-east-1"
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        config.training_instance_type = "ml.g5.xlarge"
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 0.60
        config.max_iterations = 0  # Invalid: must be >= 1
        config.cleanup_resources = True
        config.s3_bucket = "test-bucket"
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("iterations" in error.lower() for error in result.errors)


class TestValidatePipelineConfigWarnings:
    """Test suite for PipelineConfig warning conditions"""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture providing a ConfigurationManager instance"""
        return ConfigurationManager(str(tmp_path / "config"))
    
    def test_validate_pipeline_config_unusual_region_warning(self, config_manager):
        """Test that unusual AWS regions generate warnings"""
        config = PipelineConfig(
            aws_region="ap-northeast-3",  # Less common region
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("region" in warning.lower() for warning in result.warnings)

    def test_validate_pipeline_config_non_claude_model_warning(self, config_manager):
        """Test that non-Claude models generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="amazon.titan-text-express-v1",  # Not Claude
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("claude" in warning.lower() for warning in result.warnings)
    
    def test_validate_pipeline_config_non_gpu_instance_warning(self, config_manager):
        """Test that non-GPU instances generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.m5.xlarge",  # CPU instance
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("gpu" in warning.lower() for warning in result.warnings)
    
    def test_validate_pipeline_config_low_threshold_warning(self, config_manager):
        """Test that low performance thresholds generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.3,  # Low threshold
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("threshold" in warning.lower() and "low" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_pipeline_config_high_threshold_warning(self, config_manager):
        """Test that high performance thresholds generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.95,  # Very high threshold
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("threshold" in warning.lower() and "high" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_pipeline_config_many_iterations_warning(self, config_manager):
        """Test that many iterations generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=15,  # Many iterations
            cleanup_resources=True,
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("iterations" in warning.lower() and "high" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_pipeline_config_non_llama_model_warning(self, config_manager):
        """Test that non-Llama base models generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            base_model="mistral/Mistral-7B"  # Not Llama
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("llama" in warning.lower() for warning in result.warnings)
    
    def test_validate_pipeline_config_short_training_time_warning(self, config_manager):
        """Test that short training times generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            max_training_time_seconds=60  # Only 1 minute
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("training time" in warning.lower() and "short" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_pipeline_config_long_training_time_warning(self, config_manager):
        """Test that long training times generate warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            max_training_time_seconds=100000  # Very long
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("training time" in warning.lower() and "long" in warning.lower() 
                  for warning in result.warnings)
    
    def test_validate_pipeline_config_no_cleanup_warning(self, config_manager):
        """Test that disabled cleanup generates warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=False,  # Cleanup disabled
            s3_bucket="test-bucket"
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("cleanup" in warning.lower() for warning in result.warnings)
    
    def test_validate_pipeline_config_long_retention_warning(self, config_manager):
        """Test that long artifact retention generates warnings"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=3,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            artifact_retention_days=400  # Very long retention
        )
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is True
        assert any("retention" in warning.lower() and "long" in warning.lower() 
                  for warning in result.warnings)


class TestValidatePipelineConfigEdgeCases:
    """Test suite for PipelineConfig edge cases"""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture providing a ConfigurationManager instance"""
        return ConfigurationManager(str(tmp_path / "config"))
    
    def test_validate_pipeline_config_backoff_inconsistency(self, config_manager):
        """Test that max_backoff < initial_backoff is rejected"""
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = "us-east-1"
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        config.training_instance_type = "ml.g5.xlarge"
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 0.60
        config.max_iterations = 3
        config.cleanup_resources = True
        config.s3_bucket = "test-bucket"
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 10
        config.max_backoff_seconds = 5  # Less than initial
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("backoff" in error.lower() for error in result.errors)
    
    def test_validate_pipeline_config_s3_bucket_too_short(self, config_manager):
        """Test that S3 bucket names < 3 characters are rejected"""
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = "us-east-1"
        config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        config.training_instance_type = "ml.g5.xlarge"
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 0.60
        config.max_iterations = 3
        config.cleanup_resources = True
        config.s3_bucket = "ab"  # Too short
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert any("bucket" in error.lower() and "3 and 63" in error 
                  for error in result.errors)
    
    def test_validate_pipeline_config_multiple_errors(self, config_manager):
        """Test that multiple errors are all reported"""
        config = PipelineConfig.__new__(PipelineConfig)
        config.aws_region = ""  # Error 1
        config.bedrock_model_id = ""  # Error 2
        config.sagemaker_role_arn = "invalid"  # Error 3
        config.training_instance_type = "invalid"  # Error 4
        config.inference_instance_type = "ml.g5.xlarge"
        config.baseline_model_endpoint = "llama-70b-baseline"
        config.performance_threshold = 1.5  # Error 5
        config.max_iterations = 0  # Error 6
        config.cleanup_resources = True
        config.s3_bucket = "test-bucket"
        config.base_model = "meta-llama/Llama-3.2-3B"
        config.max_training_time_seconds = 3600
        config.max_retries = 3
        config.initial_backoff_seconds = 2
        config.max_backoff_seconds = 60
        config.artifact_retention_days = 7
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid is False
        assert len(result.errors) >= 6  # At least 6 errors


class TestValidationResultStructure:
    """Test suite for ValidationResult structure and methods"""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture providing a ConfigurationManager instance"""
        return ConfigurationManager(str(tmp_path / "config"))
    
    def test_validation_result_has_required_fields(self, config_manager):
        """Test that ValidationResult has all required fields"""
        use_case = UseCase(
            name="test",
            description="Valid description",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        result = config_manager.validate_config(use_case)
        
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
    
    def test_validation_result_errors_are_strings(self, config_manager):
        """Test that all errors are strings"""
        use_case = UseCase.__new__(UseCase)
        use_case.name = ""
        use_case.description = ""
        use_case.test_questions = []
        use_case.judge_criteria = ""
        use_case.data_generation_prompt = ""
        use_case.judge_prompt = ""
        use_case.version = 0
        use_case.created_at = None
        
        result = config_manager.validate_config(use_case)
        
        assert all(isinstance(error, str) for error in result.errors)
    
    def test_validation_result_warnings_are_strings(self, config_manager):
        """Test that all warnings are strings"""
        use_case = UseCase(
            name="ab",  # Short name
            description="Short",  # Short description
            test_questions=["Q1"],  # Few questions
            judge_criteria="Short",  # Short criteria
            data_generation_prompt="Short",  # Short prompt
            judge_prompt="Short"  # Short judge prompt
        )
        
        result = config_manager.validate_config(use_case)
        
        assert all(isinstance(warning, str) for warning in result.warnings)
    
    def test_validation_result_str_representation(self, config_manager):
        """Test ValidationResult string representation"""
        use_case = UseCase(
            name="test",
            description="Valid description",
            test_questions=["Q1", "Q2", "Q3"],
            judge_criteria="Criteria",
            data_generation_prompt="Prompt",
            judge_prompt="Judge"
        )
        
        result = config_manager.validate_config(use_case)
        result_str = str(result)
        
        assert isinstance(result_str, str)
        assert len(result_str) > 0
