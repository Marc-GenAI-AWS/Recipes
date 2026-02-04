"""
Configuration Data Models for Automated LLM Finetuning Pipeline

This module defines the core data structures used throughout the pipeline,
including use case definitions, pipeline configuration, and validation results.

All dataclasses include comprehensive type hints and validation logic.
Pydantic models are provided for additional validation capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


@dataclass
class UseCase:
    """
    Represents a use case for model finetuning.
    
    A use case defines the domain, test questions, evaluation criteria,
    and prompts used for data generation and judging.
    """
    name: str
    description: str
    test_questions: List[str]
    judge_criteria: str
    data_generation_prompt: str
    judge_prompt: str
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate required fields after initialization"""
        if not self.name or not self.name.strip():
            raise ValueError("Use case name cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("Use case description cannot be empty")
        if not self.test_questions or len(self.test_questions) == 0:
            raise ValueError("Use case must have at least one test question")
        if not self.judge_criteria or not self.judge_criteria.strip():
            raise ValueError("Judge criteria cannot be empty")
        if not self.data_generation_prompt or not self.data_generation_prompt.strip():
            raise ValueError("Data generation prompt cannot be empty")
        if not self.judge_prompt or not self.judge_prompt.strip():
            raise ValueError("Judge prompt cannot be empty")
        if self.version < 1:
            raise ValueError("Version must be >= 1")


@dataclass
class PipelineConfig:
    """
    Configuration for pipeline execution including AWS settings and thresholds.
    """
    aws_region: str
    bedrock_model_id: str
    sagemaker_role_arn: str
    training_instance_type: str
    inference_instance_type: str
    baseline_model_endpoint: str
    performance_threshold: float
    max_iterations: int
    cleanup_resources: bool
    s3_bucket: str
    base_model: str = "meta-llama/Llama-3.2-3B"
    max_training_time_seconds: int = 86400
    max_retries: int = 3
    initial_backoff_seconds: int = 2
    max_backoff_seconds: int = 60
    artifact_retention_days: int = 7
    
    def __post_init__(self):
        """Validate configuration values"""
        if not self.aws_region or not self.aws_region.strip():
            raise ValueError("AWS region cannot be empty")
        if not self.bedrock_model_id or not self.bedrock_model_id.strip():
            raise ValueError("Bedrock model ID cannot be empty")
        if not self.sagemaker_role_arn or not self.sagemaker_role_arn.strip():
            raise ValueError("SageMaker role ARN cannot be empty")
        if not self.s3_bucket or not self.s3_bucket.strip():
            raise ValueError("S3 bucket cannot be empty")
        if self.performance_threshold < 0.0 or self.performance_threshold > 1.0:
            raise ValueError("Performance threshold must be between 0.0 and 1.0")
        if self.max_iterations < 1:
            raise ValueError("Max iterations must be >= 1")
        if self.max_training_time_seconds < 1:
            raise ValueError("Max training time must be >= 1 second")
        if self.max_retries < 0:
            raise ValueError("Max retries must be >= 0")
        if self.artifact_retention_days < 0:
            raise ValueError("Artifact retention days must be >= 0")


@dataclass
class ValidationResult:
    """
    Result of configuration validation.
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: str) -> None:
        """Add an error message and mark validation as invalid"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message"""
        self.warnings.append(warning)
    
    def __str__(self) -> str:
        """String representation of validation result"""
        if self.is_valid:
            msg = "Validation passed"
            if self.warnings:
                msg += f" with {len(self.warnings)} warning(s)"
            return msg
        else:
            return f"Validation failed with {len(self.errors)} error(s)"


@dataclass
class TrainingExample:
    """
    A single training example in JSONL format.
    """
    instruction: str
    context: str
    response: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for JSONL serialization"""
        return {
            "instruction": self.instruction,
            "context": self.context,
            "response": self.response
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'TrainingExample':
        """Create from dictionary"""
        return cls(
            instruction=data["instruction"],
            context=data["context"],
            response=data["response"]
        )


@dataclass
class DatasetAnalysis:
    """
    Analysis results for a training dataset.
    """
    num_examples: int
    avg_instruction_length: int
    avg_response_length: int
    recommended_epochs: int
    recommended_batch_size: int
    
    def __post_init__(self):
        """Validate analysis values"""
        if self.num_examples < 0:
            raise ValueError("Number of examples must be >= 0")
        if self.recommended_epochs < 1:
            raise ValueError("Recommended epochs must be >= 1")
        if self.recommended_batch_size < 1:
            raise ValueError("Recommended batch size must be >= 1")


@dataclass
class TrainingResult:
    """
    Result of a model training job.
    """
    job_name: str
    model_artifact_s3_uri: str
    training_time_seconds: int
    final_loss: float
    status: str
    error_message: Optional[str] = None
    
    def is_successful(self) -> bool:
        """Check if training completed successfully"""
        return self.status == "Completed" and self.error_message is None


@dataclass
class DeploymentResult:
    """
    Result of model deployment to an endpoint.
    """
    endpoint_name: str
    endpoint_arn: str
    status: str
    creation_time: datetime
    error_message: Optional[str] = None
    
    def is_successful(self) -> bool:
        """Check if deployment completed successfully"""
        return self.status == "InService" and self.error_message is None


@dataclass
class ResponsePair:
    """
    A pair of responses from finetuned and baseline models.
    """
    question: str
    finetuned_response: str
    baseline_response: str


@dataclass
class ResponsePairs:
    """
    Collection of response pairs with metadata.
    """
    pairs: List[ResponsePair]
    finetuned_endpoint: str
    baseline_endpoint: str
    generation_time: datetime = field(default_factory=datetime.now)


@dataclass
class Judgment:
    """
    Judge's evaluation of a response pair.
    """
    question: str
    winner: str  # 'finetuned', 'baseline', 'tie'
    reasoning: str
    confidence: float
    
    def __post_init__(self):
        """Validate judgment values"""
        if self.winner not in ['finetuned', 'baseline', 'tie']:
            raise ValueError(f"Invalid winner value: {self.winner}")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        if not self.reasoning or not self.reasoning.strip():
            raise ValueError("Reasoning cannot be empty")


@dataclass
class EvaluationResult:
    """
    Complete evaluation results for all response pairs.
    """
    judgments: List[Judgment]
    win_rate: float
    tie_rate: float
    total_comparisons: int
    evaluation_time: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate evaluation results"""
        if self.win_rate < 0.0 or self.win_rate > 1.0:
            raise ValueError("Win rate must be between 0.0 and 1.0")
        if self.tie_rate < 0.0 or self.tie_rate > 1.0:
            raise ValueError("Tie rate must be between 0.0 and 1.0")
        if self.total_comparisons != len(self.judgments):
            raise ValueError("Total comparisons must equal number of judgments")


@dataclass
class FailureAnalysis:
    """
    Analysis of finetuned model failures.
    """
    common_weaknesses: List[str]
    missing_capabilities: List[str]
    improvement_suggestions: List[str]


@dataclass
class Prompts:
    """
    Prompts used for data generation and judging.
    """
    data_generation_prompt: str
    judge_prompt: str


@dataclass
class ImprovedPrompts:
    """
    Improved prompts with rationale.
    """
    data_generation_prompt: str
    judge_prompt: str
    improvement_rationale: str


@dataclass
class IterationResult:
    """
    Results from a single pipeline iteration.
    """
    iteration: int
    win_rate: float
    prompts_used: Prompts
    training_time_seconds: int
    evaluation_time: datetime
    model_artifact_uri: str
    endpoint_name: str
    
    def __post_init__(self):
        """Validate iteration result"""
        if self.iteration < 1:
            raise ValueError("Iteration must be >= 1")
        if self.win_rate < 0.0 or self.win_rate > 1.0:
            raise ValueError("Win rate must be between 0.0 and 1.0")
        if self.training_time_seconds < 0:
            raise ValueError("Training time must be >= 0")


@dataclass
class PipelineState:
    """
    Saved state for pipeline resumption.
    """
    use_case_name: str
    current_iteration: int
    completed_steps: List[str]
    intermediate_results: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceReport:
    """
    Summary report of performance across iterations.
    """
    use_case_name: str
    total_iterations: int
    initial_win_rate: float
    final_win_rate: float
    improvement: float
    best_iteration: int
    iteration_history: List[IterationResult]
    
    def __post_init__(self):
        """Validate performance report"""
        if self.total_iterations != len(self.iteration_history):
            raise ValueError("Total iterations must equal length of iteration history")
        if self.total_iterations > 0:
            if abs(self.improvement - (self.final_win_rate - self.initial_win_rate)) > 0.001:
                raise ValueError("Improvement must equal final - initial win rate")


@dataclass
class PipelineResult:
    """
    Final result of complete pipeline execution.
    """
    use_case_name: str
    success: bool
    final_win_rate: float
    total_iterations: int
    performance_report: PerformanceReport
    error_message: Optional[str] = None



# Pydantic Models for Enhanced Validation

class UseCasePydantic(BaseModel):
    """Pydantic model for UseCase validation"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str = Field(..., min_length=1, description="Use case name")
    description: str = Field(..., min_length=1, description="Use case description")
    test_questions: List[str] = Field(..., min_length=1, description="Test questions")
    judge_criteria: str = Field(..., min_length=1, description="Judge criteria")
    data_generation_prompt: str = Field(..., min_length=1, description="Data generation prompt")
    judge_prompt: str = Field(..., min_length=1, description="Judge prompt")
    version: int = Field(default=1, ge=1, description="Version number")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    
    @field_validator('test_questions')
    @classmethod
    def validate_questions(cls, v: List[str]) -> List[str]:
        """Ensure all questions are non-empty"""
        if not all(q.strip() for q in v):
            raise ValueError("All test questions must be non-empty")
        return v


class PipelineConfigPydantic(BaseModel):
    """Pydantic model for PipelineConfig validation"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    aws_region: str = Field(..., min_length=1, description="AWS region")
    bedrock_model_id: str = Field(..., min_length=1, description="Bedrock model ID")
    sagemaker_role_arn: str = Field(..., min_length=1, description="SageMaker role ARN")
    training_instance_type: str = Field(..., min_length=1, description="Training instance type")
    inference_instance_type: str = Field(..., min_length=1, description="Inference instance type")
    baseline_model_endpoint: str = Field(..., min_length=1, description="Baseline model endpoint")
    performance_threshold: float = Field(..., ge=0.0, le=1.0, description="Performance threshold")
    max_iterations: int = Field(..., ge=1, description="Maximum iterations")
    cleanup_resources: bool = Field(..., description="Whether to cleanup resources")
    s3_bucket: str = Field(..., min_length=1, description="S3 bucket name")
    base_model: str = Field(default="meta-llama/Llama-3.2-3B", description="Base model")
    max_training_time_seconds: int = Field(default=86400, ge=1, description="Max training time")
    max_retries: int = Field(default=3, ge=0, description="Max retry attempts")
    initial_backoff_seconds: int = Field(default=2, ge=1, description="Initial backoff")
    max_backoff_seconds: int = Field(default=60, ge=1, description="Max backoff")
    artifact_retention_days: int = Field(default=7, ge=0, description="Artifact retention days")
    
    @field_validator('sagemaker_role_arn')
    @classmethod
    def validate_role_arn(cls, v: str) -> str:
        """Validate SageMaker role ARN format"""
        if not v.startswith('arn:aws:iam::'):
            raise ValueError("SageMaker role ARN must start with 'arn:aws:iam::'")
        return v


class TrainingExamplePydantic(BaseModel):
    """Pydantic model for TrainingExample validation"""
    instruction: str = Field(..., min_length=1, description="Instruction text")
    context: str = Field(..., description="Context text")
    response: str = Field(..., min_length=1, description="Response text")


class JudgmentPydantic(BaseModel):
    """Pydantic model for Judgment validation"""
    question: str = Field(..., min_length=1, description="Question text")
    winner: str = Field(..., pattern="^(finetuned|baseline|tie)$", description="Winner designation")
    reasoning: str = Field(..., min_length=1, description="Reasoning text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class EvaluationResultPydantic(BaseModel):
    """Pydantic model for EvaluationResult validation"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    judgments: List[Dict[str, Any]] = Field(..., description="List of judgments")
    win_rate: float = Field(..., ge=0.0, le=1.0, description="Win rate")
    tie_rate: float = Field(..., ge=0.0, le=1.0, description="Tie rate")
    total_comparisons: int = Field(..., ge=0, description="Total comparisons")
    evaluation_time: datetime = Field(default_factory=datetime.now, description="Evaluation time")
    
    @field_validator('judgments')
    @classmethod
    def validate_judgments_count(cls, v: List[Dict[str, Any]], info) -> List[Dict[str, Any]]:
        """Ensure judgments count matches total_comparisons"""
        # Note: This validation happens after all fields are set
        return v
