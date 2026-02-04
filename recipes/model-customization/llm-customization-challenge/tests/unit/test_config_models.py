"""
Unit tests for configuration data models.

Tests dataclass instantiation, validation, and edge cases.
"""

import pytest
from datetime import datetime
from src.config_models import (
    UseCase, PipelineConfig, ValidationResult, TrainingExample,
    DatasetAnalysis, TrainingResult, DeploymentResult, ResponsePair,
    ResponsePairs, Judgment, EvaluationResult, FailureAnalysis,
    Prompts, ImprovedPrompts, IterationResult, PipelineState,
    PerformanceReport, PipelineResult
)


class TestUseCase:
    """Tests for UseCase dataclass"""
    
    def test_valid_use_case_creation(self):
        """Test creating a valid use case"""
        use_case = UseCase(
            name="test_case",
            description="Test description",
            test_questions=["Question 1", "Question 2"],
            judge_criteria="Test criteria",
            data_generation_prompt="Generate data",
            judge_prompt="Judge responses"
        )
        
        assert use_case.name == "test_case"
        assert use_case.description == "Test description"
        assert len(use_case.test_questions) == 2
        assert use_case.version == 1
        assert isinstance(use_case.created_at, datetime)
    
    def test_use_case_with_custom_version(self):
        """Test creating use case with custom version"""
        use_case = UseCase(
            name="test_case",
            description="Test description",
            test_questions=["Question 1"],
            judge_criteria="Test criteria",
            data_generation_prompt="Generate data",
            judge_prompt="Judge responses",
            version=5
        )
        
        assert use_case.version == 5
    
    def test_use_case_empty_name_raises_error(self):
        """Test that empty name raises ValueError"""
        with pytest.raises(ValueError, match="name cannot be empty"):
            UseCase(
                name="",
                description="Test description",
                test_questions=["Question 1"],
                judge_criteria="Test criteria",
                data_generation_prompt="Generate data",
                judge_prompt="Judge responses"
            )
    
    def test_use_case_empty_description_raises_error(self):
        """Test that empty description raises ValueError"""
        with pytest.raises(ValueError, match="description cannot be empty"):
            UseCase(
                name="test_case",
                description="",
                test_questions=["Question 1"],
                judge_criteria="Test criteria",
                data_generation_prompt="Generate data",
                judge_prompt="Judge responses"
            )
    
    def test_use_case_empty_questions_raises_error(self):
        """Test that empty questions list raises ValueError"""
        with pytest.raises(ValueError, match="at least one test question"):
            UseCase(
                name="test_case",
                description="Test description",
                test_questions=[],
                judge_criteria="Test criteria",
                data_generation_prompt="Generate data",
                judge_prompt="Judge responses"
            )
    
    def test_use_case_invalid_version_raises_error(self):
        """Test that version < 1 raises ValueError"""
        with pytest.raises(ValueError, match="Version must be >= 1"):
            UseCase(
                name="test_case",
                description="Test description",
                test_questions=["Question 1"],
                judge_criteria="Test criteria",
                data_generation_prompt="Generate data",
                judge_prompt="Judge responses",
                version=0
            )


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass"""
    
    def test_valid_pipeline_config_creation(self):
        """Test creating a valid pipeline config"""
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-bucket"
        )
        
        assert config.aws_region == "us-east-1"
        assert config.performance_threshold == 0.60
        assert config.max_iterations == 5
        assert config.base_model == "meta-llama/Llama-3.2-3B"
        assert config.max_retries == 3
    
    def test_pipeline_config_invalid_threshold_raises_error(self):
        """Test that invalid threshold raises ValueError"""
        with pytest.raises(ValueError, match="Performance threshold must be between"):
            PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id="anthropic.claude-sonnet-4",
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=1.5,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-bucket"
            )
    
    def test_pipeline_config_invalid_max_iterations_raises_error(self):
        """Test that invalid max_iterations raises ValueError"""
        with pytest.raises(ValueError, match="Max iterations must be >= 1"):
            PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id="anthropic.claude-sonnet-4",
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=0,
                cleanup_resources=True,
                s3_bucket="my-bucket"
            )


class TestValidationResult:
    """Tests for ValidationResult dataclass"""
    
    def test_valid_validation_result(self):
        """Test creating a valid validation result"""
        result = ValidationResult(is_valid=True)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_add_error_marks_invalid(self):
        """Test that adding error marks result as invalid"""
        result = ValidationResult(is_valid=True)
        result.add_error("Test error")
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
    
    def test_add_warning_preserves_validity(self):
        """Test that adding warning preserves validity"""
        result = ValidationResult(is_valid=True)
        result.add_warning("Test warning")
        
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
    
    def test_validation_result_string_representation(self):
        """Test string representation of validation result"""
        result = ValidationResult(is_valid=True)
        assert "Validation passed" in str(result)
        
        result.add_error("Error 1")
        assert "failed" in str(result)
        assert "1 error" in str(result)


class TestTrainingExample:
    """Tests for TrainingExample dataclass"""
    
    def test_training_example_creation(self):
        """Test creating a training example"""
        example = TrainingExample(
            instruction="Test instruction",
            context="Test context",
            response="Test response"
        )
        
        assert example.instruction == "Test instruction"
        assert example.context == "Test context"
        assert example.response == "Test response"
    
    def test_training_example_to_dict(self):
        """Test converting training example to dict"""
        example = TrainingExample(
            instruction="Test instruction",
            context="Test context",
            response="Test response"
        )
        
        data = example.to_dict()
        assert data["instruction"] == "Test instruction"
        assert data["context"] == "Test context"
        assert data["response"] == "Test response"
    
    def test_training_example_from_dict(self):
        """Test creating training example from dict"""
        data = {
            "instruction": "Test instruction",
            "context": "Test context",
            "response": "Test response"
        }
        
        example = TrainingExample.from_dict(data)
        assert example.instruction == "Test instruction"
        assert example.context == "Test context"
        assert example.response == "Test response"


class TestDatasetAnalysis:
    """Tests for DatasetAnalysis dataclass"""
    
    def test_dataset_analysis_creation(self):
        """Test creating dataset analysis"""
        analysis = DatasetAnalysis(
            num_examples=1000,
            avg_instruction_length=50,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=16
        )
        
        assert analysis.num_examples == 1000
        assert analysis.recommended_epochs == 3
        assert analysis.recommended_batch_size == 16
    
    def test_dataset_analysis_invalid_epochs_raises_error(self):
        """Test that invalid epochs raises ValueError"""
        with pytest.raises(ValueError, match="Recommended epochs must be >= 1"):
            DatasetAnalysis(
                num_examples=1000,
                avg_instruction_length=50,
                avg_response_length=200,
                recommended_epochs=0,
                recommended_batch_size=16
            )


class TestJudgment:
    """Tests for Judgment dataclass"""
    
    def test_valid_judgment_creation(self):
        """Test creating a valid judgment"""
        judgment = Judgment(
            question="Test question",
            winner="finetuned",
            reasoning="Finetuned model provided better response",
            confidence=0.85
        )
        
        assert judgment.winner == "finetuned"
        assert judgment.confidence == 0.85
    
    def test_judgment_invalid_winner_raises_error(self):
        """Test that invalid winner raises ValueError"""
        with pytest.raises(ValueError, match="Invalid winner value"):
            Judgment(
                question="Test question",
                winner="invalid",
                reasoning="Test reasoning",
                confidence=0.85
            )
    
    def test_judgment_invalid_confidence_raises_error(self):
        """Test that invalid confidence raises ValueError"""
        with pytest.raises(ValueError, match="Confidence must be between"):
            Judgment(
                question="Test question",
                winner="finetuned",
                reasoning="Test reasoning",
                confidence=1.5
            )
    
    def test_judgment_empty_reasoning_raises_error(self):
        """Test that empty reasoning raises ValueError"""
        with pytest.raises(ValueError, match="Reasoning cannot be empty"):
            Judgment(
                question="Test question",
                winner="finetuned",
                reasoning="",
                confidence=0.85
            )


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass"""
    
    def test_evaluation_result_creation(self):
        """Test creating evaluation result"""
        judgments = [
            Judgment("Q1", "finetuned", "Better", 0.9),
            Judgment("Q2", "baseline", "Better", 0.8)
        ]
        
        result = EvaluationResult(
            judgments=judgments,
            win_rate=0.5,
            tie_rate=0.0,
            total_comparisons=2
        )
        
        assert result.win_rate == 0.5
        assert result.total_comparisons == 2
        assert len(result.judgments) == 2
    
    def test_evaluation_result_invalid_win_rate_raises_error(self):
        """Test that invalid win rate raises ValueError"""
        with pytest.raises(ValueError, match="Win rate must be between"):
            EvaluationResult(
                judgments=[],
                win_rate=1.5,
                tie_rate=0.0,
                total_comparisons=0
            )
    
    def test_evaluation_result_mismatched_count_raises_error(self):
        """Test that mismatched count raises ValueError"""
        judgments = [
            Judgment("Q1", "finetuned", "Better", 0.9)
        ]
        
        with pytest.raises(ValueError, match="Total comparisons must equal"):
            EvaluationResult(
                judgments=judgments,
                win_rate=0.5,
                tie_rate=0.0,
                total_comparisons=2
            )


class TestIterationResult:
    """Tests for IterationResult dataclass"""
    
    def test_iteration_result_creation(self):
        """Test creating iteration result"""
        prompts = Prompts(
            data_generation_prompt="Generate data",
            judge_prompt="Judge responses"
        )
        
        result = IterationResult(
            iteration=1,
            win_rate=0.65,
            prompts_used=prompts,
            training_time_seconds=3600,
            evaluation_time=datetime.now(),
            model_artifact_uri="s3://bucket/model",
            endpoint_name="test-endpoint"
        )
        
        assert result.iteration == 1
        assert result.win_rate == 0.65
        assert result.training_time_seconds == 3600
    
    def test_iteration_result_invalid_iteration_raises_error(self):
        """Test that invalid iteration raises ValueError"""
        prompts = Prompts(
            data_generation_prompt="Generate data",
            judge_prompt="Judge responses"
        )
        
        with pytest.raises(ValueError, match="Iteration must be >= 1"):
            IterationResult(
                iteration=0,
                win_rate=0.65,
                prompts_used=prompts,
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model",
                endpoint_name="test-endpoint"
            )


class TestPerformanceReport:
    """Tests for PerformanceReport dataclass"""
    
    def test_performance_report_creation(self):
        """Test creating performance report"""
        prompts = Prompts(
            data_generation_prompt="Generate data",
            judge_prompt="Judge responses"
        )
        
        iteration1 = IterationResult(
            iteration=1,
            win_rate=0.50,
            prompts_used=prompts,
            training_time_seconds=3600,
            evaluation_time=datetime.now(),
            model_artifact_uri="s3://bucket/model1",
            endpoint_name="endpoint1"
        )
        
        iteration2 = IterationResult(
            iteration=2,
            win_rate=0.65,
            prompts_used=prompts,
            training_time_seconds=3600,
            evaluation_time=datetime.now(),
            model_artifact_uri="s3://bucket/model2",
            endpoint_name="endpoint2"
        )
        
        report = PerformanceReport(
            use_case_name="test_case",
            total_iterations=2,
            initial_win_rate=0.50,
            final_win_rate=0.65,
            improvement=0.15,
            best_iteration=2,
            iteration_history=[iteration1, iteration2]
        )
        
        assert report.total_iterations == 2
        assert report.improvement == 0.15
        assert len(report.iteration_history) == 2
    
    def test_performance_report_invalid_improvement_raises_error(self):
        """Test that invalid improvement calculation raises ValueError"""
        prompts = Prompts(
            data_generation_prompt="Generate data",
            judge_prompt="Judge responses"
        )
        
        iteration1 = IterationResult(
            iteration=1,
            win_rate=0.50,
            prompts_used=prompts,
            training_time_seconds=3600,
            evaluation_time=datetime.now(),
            model_artifact_uri="s3://bucket/model1",
            endpoint_name="endpoint1"
        )
        
        with pytest.raises(ValueError, match="Improvement must equal"):
            PerformanceReport(
                use_case_name="test_case",
                total_iterations=1,
                initial_win_rate=0.50,
                final_win_rate=0.65,
                improvement=0.20,  # Wrong value
                best_iteration=1,
                iteration_history=[iteration1]
            )


class TestTrainingResult:
    """Tests for TrainingResult dataclass"""
    
    def test_training_result_successful(self):
        """Test successful training result"""
        result = TrainingResult(
            job_name="test-job",
            model_artifact_s3_uri="s3://bucket/model",
            training_time_seconds=3600,
            final_loss=0.25,
            status="Completed"
        )
        
        assert result.is_successful() is True
    
    def test_training_result_failed(self):
        """Test failed training result"""
        result = TrainingResult(
            job_name="test-job",
            model_artifact_s3_uri="s3://bucket/model",
            training_time_seconds=3600,
            final_loss=0.25,
            status="Failed",
            error_message="Training failed"
        )
        
        assert result.is_successful() is False


class TestDeploymentResult:
    """Tests for DeploymentResult dataclass"""
    
    def test_deployment_result_successful(self):
        """Test successful deployment result"""
        result = DeploymentResult(
            endpoint_name="test-endpoint",
            endpoint_arn="arn:aws:sagemaker:us-east-1:123456789012:endpoint/test",
            status="InService",
            creation_time=datetime.now()
        )
        
        assert result.is_successful() is True
    
    def test_deployment_result_failed(self):
        """Test failed deployment result"""
        result = DeploymentResult(
            endpoint_name="test-endpoint",
            endpoint_arn="arn:aws:sagemaker:us-east-1:123456789012:endpoint/test",
            status="Failed",
            creation_time=datetime.now(),
            error_message="Deployment failed"
        )
        
        assert result.is_successful() is False
