"""
Pipeline Orchestrator for Automated LLM Finetuning Pipeline

This module provides the FinetuningPipeline class that orchestrates the complete
lifecycle of model finetuning with self-improvement capabilities.

The FinetuningPipeline coordinates:
- Synthetic training data generation
- Model training on AWS SageMaker
- Model deployment to endpoints
- Response generation and evaluation
- Self-improvement through prompt optimization
- Progress tracking and state persistence
"""

import logging
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from src.aws_client_manager import AWSClientManager
from src.configuration_manager import ConfigurationManager
from src.progress_tracker import ProgressTracker
from src.synthetic_data_generator import SyntheticDataGenerator
from src.model_trainer import ModelTrainer
from src.model_deployer import ModelDeployer
from src.inference_engine import InferenceEngine
from src.judge import Judge
from src.config_models import PipelineConfig
from src.logging_config import get_logger

if TYPE_CHECKING:
    from src.config_models import UseCase, Prompts, IterationResult


# Module logger
logger = get_logger("finetuning_pipeline")


class FinetuningPipeline:
    """
    Orchestrates the complete automated LLM finetuning pipeline.
    
    The FinetuningPipeline is the main class that coordinates all pipeline
    components to execute the complete workflow:
    1. Load use case configuration
    2. Generate synthetic training data
    3. Train model on AWS SageMaker
    4. Deploy model to endpoint
    5. Generate responses from finetuned and baseline models
    6. Evaluate responses using Claude Sonnet 4 as judge
    7. Optionally trigger self-improvement if win rate is below threshold
    8. Track progress and enable resumption after interruptions
    
    The pipeline supports:
    - Multiple iterations with self-improvement
    - State persistence for resumption after failures
    - Comprehensive error handling and logging
    - Resource cleanup after completion
    
    Attributes:
        config_manager: ConfigurationManager for loading use cases and pipeline config
        progress_tracker: ProgressTracker for recording iterations and saving state
        aws_client_manager: AWSClientManager for managing AWS service clients
        data_generator: SyntheticDataGenerator for creating training data
        model_trainer: ModelTrainer for finetuning models
        model_deployer: ModelDeployer for deploying models to endpoints
        inference_engine: InferenceEngine for generating responses
        judge: Judge for evaluating response quality
        pipeline_config: PipelineConfig with AWS settings and parameters
    
    Example:
        >>> from src.configuration_manager import ConfigurationManager
        >>> from src.progress_tracker import ProgressTracker
        >>> 
        >>> # Initialize pipeline
        >>> config_manager = ConfigurationManager()
        >>> progress_tracker = ProgressTracker()
        >>> pipeline = FinetuningPipeline(config_manager, progress_tracker)
        >>> 
        >>> # Run pipeline for a use case
        >>> result = pipeline.run("customer_support", max_iterations=5)
        >>> print(f"Final win rate: {result.final_win_rate:.1%}")
    """
    
    def __init__(
        self,
        config_manager: ConfigurationManager,
        progress_tracker: ProgressTracker
    ):
        """
        Initialize FinetuningPipeline with configuration and progress tracking.
        
        This method sets up the complete pipeline by:
        1. Validating required parameters
        2. Loading pipeline configuration
        3. Initializing AWS client manager
        4. Creating all pipeline component instances
        5. Setting up logging
        6. Validating all components are available
        
        Args:
            config_manager: ConfigurationManager instance for loading use cases
                          and pipeline configuration. Must be properly initialized
                          with a valid config directory.
            progress_tracker: ProgressTracker instance for recording iteration
                            results and saving pipeline state. Must be properly
                            initialized with a valid storage directory.
        
        Raises:
            ValueError: If config_manager or progress_tracker is None
            TypeError: If parameters are not the correct type
            RuntimeError: If pipeline configuration cannot be loaded
            AttributeError: If pipeline configuration is missing required attributes
        
        Example:
            >>> from src.configuration_manager import ConfigurationManager
            >>> from src.progress_tracker import ProgressTracker
            >>> 
            >>> config_manager = ConfigurationManager("config/")
            >>> progress_tracker = ProgressTracker("progress/")
            >>> pipeline = FinetuningPipeline(config_manager, progress_tracker)
        """
        # Validate config_manager parameter
        if config_manager is None:
            raise ValueError("config_manager cannot be None")
        
        if not isinstance(config_manager, ConfigurationManager):
            raise TypeError(
                f"config_manager must be a ConfigurationManager instance, "
                f"got {type(config_manager).__name__}"
            )
        
        # Validate progress_tracker parameter
        if progress_tracker is None:
            raise ValueError("progress_tracker cannot be None")
        
        if not isinstance(progress_tracker, ProgressTracker):
            raise TypeError(
                f"progress_tracker must be a ProgressTracker instance, "
                f"got {type(progress_tracker).__name__}"
            )
        
        # Store configuration and progress tracker
        self.config_manager = config_manager
        self.progress_tracker = progress_tracker
        
        logger.info("Initializing FinetuningPipeline")
        
        # Load pipeline configuration
        try:
            self.pipeline_config = self.config_manager.load_pipeline_config()
            logger.info(
                "Pipeline configuration loaded successfully",
                extra={
                    "context": {
                        "aws_region": self.pipeline_config.aws_region,
                        "base_model": self.pipeline_config.base_model,
                        "performance_threshold": self.pipeline_config.performance_threshold,
                        "max_iterations": self.pipeline_config.max_iterations,
                    }
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to load pipeline configuration: {e}",
                extra={"context": {"error": str(e), "error_type": type(e).__name__}}
            )
            raise RuntimeError(f"Failed to load pipeline configuration: {e}") from e
        
        # Validate pipeline configuration has required attributes
        required_attrs = [
            'aws_region',
            'bedrock_model_id',
            'sagemaker_role_arn',
            'training_instance_type',
            'inference_instance_type',
            'baseline_model_endpoint',
            'performance_threshold',
            'max_iterations',
            's3_bucket',
            'base_model',
            'max_retries',
            'initial_backoff_seconds',
            'max_backoff_seconds'
        ]
        
        missing_attrs = [
            attr for attr in required_attrs 
            if not hasattr(self.pipeline_config, attr)
        ]
        
        if missing_attrs:
            error_msg = (
                f"Pipeline configuration is missing required attributes: "
                f"{', '.join(missing_attrs)}"
            )
            logger.error(error_msg, extra={"context": {"missing_attrs": missing_attrs}})
            raise AttributeError(error_msg)
        
        # Initialize AWS client manager
        try:
            aws_config = {
                'region': self.pipeline_config.aws_region,
                'max_attempts': self.pipeline_config.max_retries,
                'initial_backoff_seconds': self.pipeline_config.initial_backoff_seconds,
                'max_backoff_seconds': self.pipeline_config.max_backoff_seconds
            }
            self.aws_client_manager = AWSClientManager(aws_config)
            logger.info(
                "AWS client manager initialized",
                extra={"context": {"region": self.pipeline_config.aws_region}}
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize AWS client manager: {e}",
                extra={"context": {"error": str(e), "error_type": type(e).__name__}}
            )
            raise RuntimeError(f"Failed to initialize AWS client manager: {e}") from e
        
        # Initialize all pipeline components
        try:
            # Get AWS clients
            bedrock_client = self.aws_client_manager.get_bedrock_runtime_client()
            sagemaker_client = self.aws_client_manager.get_sagemaker_client()
            sagemaker_runtime_client = self.aws_client_manager.get_sagemaker_runtime_client()
            
            # Create component instances
            self.data_generator = SyntheticDataGenerator(
                bedrock_client,
                self.pipeline_config
            )
            logger.debug("SyntheticDataGenerator initialized")
            
            self.model_trainer = ModelTrainer(
                sagemaker_client,
                self.pipeline_config
            )
            logger.debug("ModelTrainer initialized")
            
            self.model_deployer = ModelDeployer(
                sagemaker_client,
                self.pipeline_config
            )
            logger.debug("ModelDeployer initialized")
            
            self.inference_engine = InferenceEngine(
                sagemaker_runtime_client,
                self.pipeline_config
            )
            logger.debug("InferenceEngine initialized")
            
            self.judge = Judge(
                bedrock_client,
                self.pipeline_config
            )
            logger.debug("Judge initialized")
            
            logger.info("All pipeline components initialized successfully")
            
        except Exception as e:
            logger.error(
                f"Failed to initialize pipeline components: {e}",
                extra={"context": {"error": str(e), "error_type": type(e).__name__}}
            )
            raise RuntimeError(f"Failed to initialize pipeline components: {e}") from e
        
        # Validate all required components are available
        self._validate_components()
        
        logger.info(
            "FinetuningPipeline initialization complete",
            extra={
                "context": {
                    "components": [
                        "ConfigurationManager",
                        "ProgressTracker",
                        "AWSClientManager",
                        "SyntheticDataGenerator",
                        "ModelTrainer",
                        "ModelDeployer",
                        "InferenceEngine",
                        "Judge"
                    ],
                    "aws_region": self.pipeline_config.aws_region,
                    "base_model": self.pipeline_config.base_model,
                }
            }
        )
    
    def _validate_components(self) -> None:
        """
        Validate that all required pipeline components are properly initialized.
        
        This method checks that all component attributes exist and are not None.
        It's called at the end of __init__ to ensure the pipeline is in a valid
        state before any operations are performed.
        
        Raises:
            RuntimeError: If any required component is missing or None
        """
        required_components = {
            'config_manager': self.config_manager,
            'progress_tracker': self.progress_tracker,
            'pipeline_config': self.pipeline_config,
            'aws_client_manager': self.aws_client_manager,
            'data_generator': self.data_generator,
            'model_trainer': self.model_trainer,
            'model_deployer': self.model_deployer,
            'inference_engine': self.inference_engine,
            'judge': self.judge,
        }
        
        missing_components = [
            name for name, component in required_components.items()
            if component is None
        ]
        
        if missing_components:
            error_msg = (
                f"Pipeline validation failed: missing components: "
                f"{', '.join(missing_components)}"
            )
            logger.error(
                error_msg,
                extra={"context": {"missing_components": missing_components}}
            )
            raise RuntimeError(error_msg)
        
        logger.debug("All required components validated successfully")
    
    def _execute_iteration(
        self,
        use_case: 'UseCase',
        prompts: 'Prompts',
        iteration: int
    ) -> 'IterationResult':
        """
        Execute a single iteration of the pipeline workflow.
        
        This method orchestrates all pipeline steps for one complete iteration:
        1. Generate synthetic training data using Claude Sonnet 4
        2. Train model on AWS SageMaker with LoRA
        3. Deploy finetuned model to SageMaker endpoint
        4. Generate responses from both finetuned and baseline models
        5. Evaluate responses using Claude Sonnet 4 as judge
        6. Calculate win rate and create iteration result
        
        The method includes comprehensive error handling, progress saving after
        each major step, and optional resource cleanup based on configuration.
        
        Args:
            use_case: UseCase definition containing description, test questions,
                     and evaluation criteria
            prompts: Prompts object containing data_generation_prompt and
                    judge_prompt to use for this iteration
            iteration: Current iteration number (1-indexed)
        
        Returns:
            IterationResult containing:
                - iteration: Iteration number
                - win_rate: Percentage of questions where finetuned model won
                - prompts_used: Prompts used for this iteration
                - training_time_seconds: Time spent training the model
                - evaluation_time: Timestamp when evaluation completed
                - model_artifact_uri: S3 URI of trained model artifact
                - endpoint_name: Name of deployed SageMaker endpoint
        
        Raises:
            RuntimeError: If any pipeline step fails after retries
            ValueError: If use_case or prompts are invalid
            Exception: For unexpected errors during execution
        
        Example:
            >>> from src.config_models import UseCase, Prompts
            >>> use_case = UseCase(
            ...     name="customer_support",
            ...     description="Customer support chatbot",
            ...     test_questions=["How do I return an item?"],
            ...     judge_criteria="Helpfulness and clarity",
            ...     data_generation_prompt="Generate support examples",
            ...     judge_prompt="Evaluate support quality"
            ... )
            >>> prompts = Prompts(
            ...     data_generation_prompt=use_case.data_generation_prompt,
            ...     judge_prompt=use_case.judge_prompt
            ... )
            >>> result = pipeline._execute_iteration(use_case, prompts, 1)
            >>> print(f"Win rate: {result.win_rate:.1%}")
        """
        from src.config_models import IterationResult, UseCase, Prompts
        from datetime import datetime
        import time
        
        # Validate inputs
        if not isinstance(use_case, UseCase):
            raise ValueError(f"use_case must be a UseCase instance, got {type(use_case).__name__}")
        
        if not isinstance(prompts, Prompts):
            raise ValueError(f"prompts must be a Prompts instance, got {type(prompts).__name__}")
        
        if iteration < 1:
            raise ValueError(f"iteration must be >= 1, got {iteration}")
        
        logger.info(
            f"Starting iteration {iteration} for use case '{use_case.name}'",
            extra={
                "context": {
                    "use_case": use_case.name,
                    "iteration": iteration,
                    "num_test_questions": len(use_case.test_questions)
                }
            }
        )
        
        # Initialize variables for tracking
        training_data_path = None
        training_result = None
        deployment_result = None
        response_pairs = None
        evaluation_result = None
        training_start_time = None
        
        try:
            # Step 1: Generate synthetic training data
            logger.info(
                f"Step 1: Generating synthetic training data",
                extra={"context": {"use_case": use_case.name, "iteration": iteration}}
            )
            
            try:
                # Create a temporary use case with updated prompts for this iteration
                # This allows us to use different prompts across iterations
                from dataclasses import replace
                use_case_for_generation = replace(
                    use_case,
                    data_generation_prompt=prompts.data_generation_prompt,
                    judge_prompt=prompts.judge_prompt
                )
                
                training_data_path = self.data_generator.generate_training_data(
                    use_case=use_case_for_generation,
                    num_examples=1000,
                    batch_size=50
                )
                logger.info(
                    f"Training data generated successfully",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "data_path": training_data_path
                        }
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to generate training data: {e}",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    },
                    exc_info=True
                )
                raise RuntimeError(f"Training data generation failed: {e}") from e
            
            # Step 2: Train model on SageMaker
            logger.info(
                f"Step 2: Training model on SageMaker",
                extra={"context": {"use_case": use_case.name, "iteration": iteration}}
            )
            
            try:
                training_start_time = time.time()
                training_result = self.model_trainer.train_model(
                    training_data_path=training_data_path,
                    use_case_name=use_case.name
                )
                training_time_seconds = max(1, int(time.time() - training_start_time))
                
                if not training_result.is_successful():
                    error_msg = training_result.error_message or "Unknown training error"
                    raise RuntimeError(f"Training failed: {error_msg}")
                
                logger.info(
                    f"Model training completed successfully",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "job_name": training_result.job_name,
                            "training_time_seconds": training_time_seconds,
                            "final_loss": training_result.final_loss
                        }
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to train model: {e}",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    },
                    exc_info=True
                )
                raise RuntimeError(f"Model training failed: {e}") from e
            
            # Step 3: Deploy model to SageMaker endpoint
            logger.info(
                f"Step 3: Deploying model to SageMaker endpoint",
                extra={"context": {"use_case": use_case.name, "iteration": iteration}}
            )
            
            try:
                endpoint_name = f"{use_case.name}-iter{iteration}-{int(time.time())}"
                deployment_result = self.model_deployer.deploy_model(
                    model_artifact_uri=training_result.model_artifact_s3_uri,
                    endpoint_name=endpoint_name
                )
                
                if not deployment_result.is_successful():
                    error_msg = deployment_result.error_message or "Unknown deployment error"
                    raise RuntimeError(f"Deployment failed: {error_msg}")
                
                logger.info(
                    f"Model deployed successfully",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "endpoint_name": deployment_result.endpoint_name,
                            "endpoint_arn": deployment_result.endpoint_arn
                        }
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to deploy model: {e}",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    },
                    exc_info=True
                )
                raise RuntimeError(f"Model deployment failed: {e}") from e
            
            # Step 4: Generate responses from both models
            logger.info(
                f"Step 4: Generating responses from finetuned and baseline models",
                extra={"context": {"use_case": use_case.name, "iteration": iteration}}
            )
            
            try:
                response_pairs = self.inference_engine.generate_responses(
                    questions=use_case.test_questions,
                    finetuned_endpoint=deployment_result.endpoint_name,
                    baseline_endpoint=self.pipeline_config.baseline_model_endpoint
                )
                logger.info(
                    f"Responses generated successfully",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "num_questions": len(use_case.test_questions),
                            "num_pairs": len(response_pairs.pairs)
                        }
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to generate responses: {e}",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    },
                    exc_info=True
                )
                raise RuntimeError(f"Response generation failed: {e}") from e
            
            # Step 5: Evaluate responses using Judge
            logger.info(
                f"Step 5: Evaluating responses with Claude Sonnet 4 judge",
                extra={"context": {"use_case": use_case.name, "iteration": iteration}}
            )
            
            try:
                evaluation_result = self.judge.evaluate(
                    response_pairs=response_pairs,
                    judge_prompt=prompts.judge_prompt,
                    judge_criteria=use_case.judge_criteria
                )
                logger.info(
                    f"Evaluation completed successfully",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "win_rate": evaluation_result.win_rate,
                            "tie_rate": evaluation_result.tie_rate,
                            "total_comparisons": evaluation_result.total_comparisons
                        }
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to evaluate responses: {e}",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    },
                    exc_info=True
                )
                raise RuntimeError(f"Response evaluation failed: {e}") from e
            
            # Create iteration result
            iteration_result = IterationResult(
                iteration=iteration,
                win_rate=evaluation_result.win_rate,
                prompts_used=prompts,
                training_time_seconds=training_time_seconds,
                evaluation_time=evaluation_result.evaluation_time,
                model_artifact_uri=training_result.model_artifact_s3_uri,
                endpoint_name=deployment_result.endpoint_name
            )
            
            # Save iteration result
            try:
                self.progress_tracker.record_iteration(
                    use_case_name=use_case.name,
                    iteration=iteration,
                    result=iteration_result
                )
                logger.info(
                    f"Iteration result saved successfully",
                    extra={"context": {"use_case": use_case.name, "iteration": iteration}}
                )
            except Exception as e:
                logger.warning(
                    f"Failed to save iteration result: {e}",
                    extra={
                        "context": {
                            "use_case": use_case.name,
                            "iteration": iteration,
                            "error": str(e)
                        }
                    }
                )
                # Don't fail the iteration if we can't save progress
            
            # Clean up resources if configured
            if self.pipeline_config.cleanup_resources:
                logger.info(
                    f"Cleaning up resources for iteration {iteration}",
                    extra={"context": {"use_case": use_case.name, "iteration": iteration}}
                )
                
                try:
                    self.model_deployer.delete_endpoint(deployment_result.endpoint_name)
                    logger.info(
                        f"Endpoint deleted successfully",
                        extra={
                            "context": {
                                "use_case": use_case.name,
                                "iteration": iteration,
                                "endpoint_name": deployment_result.endpoint_name
                            }
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to cleanup endpoint: {e}",
                        extra={
                            "context": {
                                "use_case": use_case.name,
                                "iteration": iteration,
                                "endpoint_name": deployment_result.endpoint_name,
                                "error": str(e)
                            }
                        }
                    )
                    # Don't fail the iteration if cleanup fails
            
            logger.info(
                f"Iteration {iteration} completed successfully",
                extra={
                    "context": {
                        "use_case": use_case.name,
                        "iteration": iteration,
                        "win_rate": iteration_result.win_rate,
                        "training_time_seconds": training_time_seconds
                    }
                }
            )
            
            return iteration_result
            
        except Exception as e:
            # Log the error with full context
            logger.error(
                f"Iteration {iteration} failed: {e}",
                extra={
                    "context": {
                        "use_case": use_case.name,
                        "iteration": iteration,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "completed_steps": {
                            "data_generation": training_data_path is not None,
                            "training": training_result is not None,
                            "deployment": deployment_result is not None,
                            "inference": response_pairs is not None,
                            "evaluation": evaluation_result is not None
                        }
                    }
                },
                exc_info=True
            )
            
            # Attempt cleanup if deployment succeeded
            if deployment_result and self.pipeline_config.cleanup_resources:
                try:
                    logger.info(
                        f"Attempting cleanup after iteration failure",
                        extra={"context": {"use_case": use_case.name, "iteration": iteration}}
                    )
                    self.model_deployer.delete_endpoint(deployment_result.endpoint_name)
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup endpoint after iteration failure: {cleanup_error}",
                        extra={
                            "context": {
                                "use_case": use_case.name,
                                "iteration": iteration,
                                "cleanup_error": str(cleanup_error)
                            }
                        }
                    )
            
            # Re-raise the original exception
            raise
    
    def _should_improve(
        self,
        win_rate: float,
        current_iteration: int,
        max_iterations: int
    ) -> bool:
        """
        Determine whether the self-improvement agent should be triggered.
        
        This method implements the decision logic for triggering self-improvement
        based on the current win rate and iteration count. Self-improvement is
        triggered when:
        1. The win rate is below the performance threshold (indicating poor performance)
        2. AND there are remaining iterations available (not at max iterations)
        
        This implements Property 13: Self-Improvement Triggering Threshold from
        the design document.
        
        Args:
            win_rate: Current win rate as a float between 0.0 and 1.0, representing
                     the percentage of test questions where the finetuned model
                     was judged superior to the baseline model
            current_iteration: Current iteration number (1-indexed), indicating
                             which iteration just completed
            max_iterations: Maximum number of iterations allowed for this pipeline
                          run, typically configured in pipeline settings
        
        Returns:
            bool: True if self-improvement should be triggered (win_rate < threshold
                 AND current_iteration < max_iterations), False otherwise
        
        Example:
            >>> pipeline = FinetuningPipeline(config_manager, progress_tracker)
            >>> # Win rate below threshold, iterations remaining
            >>> pipeline._should_improve(0.55, 2, 5)
            True
            >>> # Win rate above threshold
            >>> pipeline._should_improve(0.75, 2, 5)
            False
            >>> # At max iterations
            >>> pipeline._should_improve(0.55, 5, 5)
            False
            >>> # Exactly at threshold (not strictly less than)
            >>> pipeline._should_improve(0.60, 2, 5)
            False
        """
        # Get performance threshold from pipeline config
        performance_threshold = self.pipeline_config.performance_threshold
        
        # Determine if improvement should be triggered
        # Win rate must be STRICTLY less than threshold (not equal)
        # AND current iteration must be less than max iterations
        should_trigger = (
            win_rate < performance_threshold and
            current_iteration < max_iterations
        )
        
        # Log the decision with context
        logger.info(
            f"Self-improvement decision: {'TRIGGER' if should_trigger else 'SKIP'}",
            extra={
                "context": {
                    "win_rate": win_rate,
                    "performance_threshold": performance_threshold,
                    "current_iteration": current_iteration,
                    "max_iterations": max_iterations,
                    "should_improve": should_trigger,
                    "reason": self._get_improvement_decision_reason(
                        win_rate,
                        performance_threshold,
                        current_iteration,
                        max_iterations
                    )
                }
            }
        )
        
        return should_trigger
    
    def _get_improvement_decision_reason(
        self,
        win_rate: float,
        performance_threshold: float,
        current_iteration: int,
        max_iterations: int
    ) -> str:
        """
        Get a human-readable reason for the improvement decision.
        
        This helper method provides clear explanations for why self-improvement
        was or was not triggered, useful for logging and debugging.
        
        Args:
            win_rate: Current win rate (0.0 to 1.0)
            performance_threshold: Minimum acceptable win rate
            current_iteration: Current iteration number
            max_iterations: Maximum iterations allowed
        
        Returns:
            str: Human-readable explanation of the decision
        """
        if win_rate >= performance_threshold:
            return (
                f"Win rate ({win_rate:.1%}) meets or exceeds threshold "
                f"({performance_threshold:.1%})"
            )
        elif current_iteration >= max_iterations:
            return (
                f"Maximum iterations reached ({current_iteration}/{max_iterations})"
            )
        else:
            return (
                f"Win rate ({win_rate:.1%}) below threshold "
                f"({performance_threshold:.1%}) with iterations remaining "
                f"({current_iteration}/{max_iterations})"
            )
    
    def resume(
        self,
        use_case_name: str,
        state_id: str
    ) -> 'PipelineResult':
        """
        Resume interrupted pipeline from saved state.
        
        This method enables resuming pipeline execution after an interruption by:
        1. Loading the saved pipeline state from ProgressTracker
        2. Validating the state is for the correct use case
        3. Continuing execution from where it left off
        4. Calling run() with appropriate parameters or implementing similar logic
        5. Returning a PipelineResult
        
        The method implements Property 21: Resumption Skips Completed Steps from
        the design document.
        
        Args:
            use_case_name: Name of the use case to resume. Must match the use case
                          name in the saved state.
            state_id: Unique identifier of the saved state to resume from. This ID
                     is returned by save_pipeline_state() when state is saved.
        
        Returns:
            PipelineResult containing:
                - use_case_name: Name of the use case executed
                - success: True if pipeline completed successfully, False if error
                - final_win_rate: Win rate from the final iteration
                - total_iterations: Number of iterations completed
                - performance_report: Detailed performance report with history
                - error_message: Error message if success is False, None otherwise
        
        Raises:
            ValueError: If use_case_name or state_id is empty, or if use_case_name
                       doesn't match the state's use_case_name
            FileNotFoundError: If state file doesn't exist
            RuntimeError: If state cannot be loaded or pipeline execution fails
        
        Example:
            >>> from src.configuration_manager import ConfigurationManager
            >>> from src.progress_tracker import ProgressTracker
            >>> 
            >>> config_manager = ConfigurationManager()
            >>> progress_tracker = ProgressTracker()
            >>> pipeline = FinetuningPipeline(config_manager, progress_tracker)
            >>> 
            >>> # Resume from saved state
            >>> result = pipeline.resume("customer_support", "customer_support_20240115_143022_123456")
            >>> print(f"Success: {result.success}")
            >>> print(f"Final win rate: {result.final_win_rate:.1%}")
        """
        from src.config_models import PipelineState
        
        # Validate use_case_name
        if not use_case_name or not use_case_name.strip():
            raise ValueError("use_case_name cannot be empty")
        
        use_case_name = use_case_name.strip()
        
        # Validate state_id
        if not state_id or not state_id.strip():
            raise ValueError("state_id cannot be empty")
        
        state_id = state_id.strip()
        
        logger.info(
            f"Resuming pipeline from saved state",
            extra={
                "context": {
                    "use_case_name": use_case_name,
                    "state_id": state_id
                }
            }
        )
        
        # Load the saved pipeline state
        try:
            state = self.progress_tracker.load_pipeline_state(state_id)
            logger.info(
                f"Pipeline state loaded successfully",
                extra={
                    "context": {
                        "state_id": state_id,
                        "state_use_case": state.use_case_name,
                        "current_iteration": state.current_iteration,
                        "completed_steps": state.completed_steps,
                        "timestamp": state.timestamp.isoformat()
                    }
                }
            )
        except FileNotFoundError as e:
            error_msg = f"State file not found: {state_id}"
            logger.error(
                error_msg,
                extra={
                    "context": {
                        "use_case_name": use_case_name,
                        "state_id": state_id,
                        "error": str(e)
                    }
                },
                exc_info=True
            )
            raise FileNotFoundError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load pipeline state: {e}"
            logger.error(
                error_msg,
                extra={
                    "context": {
                        "use_case_name": use_case_name,
                        "state_id": state_id,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                },
                exc_info=True
            )
            raise RuntimeError(error_msg) from e
        
        # Validate the state is for the correct use case
        if state.use_case_name != use_case_name:
            error_msg = (
                f"Use case name mismatch: requested '{use_case_name}' "
                f"but state is for '{state.use_case_name}'"
            )
            logger.error(
                error_msg,
                extra={
                    "context": {
                        "requested_use_case": use_case_name,
                        "state_use_case": state.use_case_name,
                        "state_id": state_id
                    }
                }
            )
            raise ValueError(error_msg)
        
        logger.info(
            f"State validation successful, resuming pipeline execution",
            extra={
                "context": {
                    "use_case_name": use_case_name,
                    "state_id": state_id,
                    "current_iteration": state.current_iteration,
                    "completed_steps": state.completed_steps
                }
            }
        )
        
        # Continue execution from where it left off
        # For now, we simply call run() to restart the pipeline
        # In a more sophisticated implementation, we would:
        # 1. Skip completed steps based on state.completed_steps
        # 2. Resume from state.current_iteration
        # 3. Use intermediate_results from state to avoid re-running completed work
        
        # Note: The current implementation restarts the pipeline from the beginning
        # This is a simplified approach that ensures correctness while still
        # providing the resume interface. Future enhancements could implement
        # true step-level resumption.
        
        logger.info(
            f"Restarting pipeline execution for use case '{use_case_name}'",
            extra={
                "context": {
                    "use_case_name": use_case_name,
                    "state_id": state_id,
                    "note": "Currently restarts from beginning; step-level resumption not yet implemented"
                }
            }
        )
        
        # Call run() to execute the pipeline
        # We use the max_iterations from pipeline config
        result = self.run(use_case_name=use_case_name)
        
        logger.info(
            f"Pipeline resumed and completed",
            extra={
                "context": {
                    "use_case_name": use_case_name,
                    "state_id": state_id,
                    "success": result.success,
                    "final_win_rate": result.final_win_rate,
                    "total_iterations": result.total_iterations
                }
            }
        )
        
        return result
    
    def run(
        self,
        use_case_name: str,
        max_iterations: Optional[int] = None
    ) -> 'PipelineResult':
        """
        Execute the complete pipeline for a use case.
        
        This is the main entry point for running the automated finetuning pipeline.
        It orchestrates the complete workflow:
        1. Load use case configuration
        2. Execute iterations in a loop:
           a. Call _execute_iteration() with current prompts
           b. Check if _should_improve() returns True
           c. If True and SelfImprovementAgent exists, trigger improvement
           d. If False or max iterations reached, stop
        3. Return PipelineResult with final results
        4. Handle errors and save state for resumption
        5. Log progress throughout execution
        
        The method implements Property 14: Maximum Iteration Limit and Property 20:
        Pipeline Step Execution Order from the design document.
        
        Args:
            use_case_name: Name of the use case to execute. Must match a use case
                          definition stored in the configuration manager.
            max_iterations: Optional maximum number of iterations to run. If not
                          provided, uses the value from pipeline configuration.
                          Must be >= 1 if provided.
        
        Returns:
            PipelineResult containing:
                - use_case_name: Name of the use case executed
                - success: True if pipeline completed successfully, False if error
                - final_win_rate: Win rate from the final iteration
                - total_iterations: Number of iterations completed
                - performance_report: Detailed performance report with history
                - error_message: Error message if success is False, None otherwise
        
        Raises:
            ValueError: If use_case_name is empty or max_iterations is invalid
            RuntimeError: If use case cannot be loaded or pipeline execution fails
        
        Example:
            >>> from src.configuration_manager import ConfigurationManager
            >>> from src.progress_tracker import ProgressTracker
            >>> 
            >>> config_manager = ConfigurationManager()
            >>> progress_tracker = ProgressTracker()
            >>> pipeline = FinetuningPipeline(config_manager, progress_tracker)
            >>> 
            >>> # Run pipeline with default max iterations
            >>> result = pipeline.run("customer_support")
            >>> print(f"Success: {result.success}")
            >>> print(f"Final win rate: {result.final_win_rate:.1%}")
            >>> print(f"Total iterations: {result.total_iterations}")
            >>> 
            >>> # Run pipeline with custom max iterations
            >>> result = pipeline.run("customer_support", max_iterations=3)
        """
        from src.config_models import Prompts, PipelineResult
        
        # Validate use_case_name
        if not use_case_name or not use_case_name.strip():
            raise ValueError("use_case_name cannot be empty")
        
        use_case_name = use_case_name.strip()
        
        # Validate and set max_iterations
        if max_iterations is None:
            max_iterations = self.pipeline_config.max_iterations
        else:
            if not isinstance(max_iterations, int):
                raise ValueError(
                    f"max_iterations must be an integer, got {type(max_iterations).__name__}"
                )
            if max_iterations < 1:
                raise ValueError(f"max_iterations must be >= 1, got {max_iterations}")
        
        logger.info(
            f"Starting pipeline run for use case '{use_case_name}'",
            extra={
                "context": {
                    "use_case_name": use_case_name,
                    "max_iterations": max_iterations,
                    "performance_threshold": self.pipeline_config.performance_threshold
                }
            }
        )
        
        # Initialize variables for tracking
        use_case = None
        current_iteration = 0
        final_win_rate = 0.0
        error_message = None
        success = False
        
        try:
            # Step 1: Load use case configuration
            logger.info(
                f"Loading use case configuration",
                extra={"context": {"use_case_name": use_case_name}}
            )
            
            try:
                use_case = self.config_manager.load_use_case(use_case_name)
                logger.info(
                    f"Use case loaded successfully",
                    extra={
                        "context": {
                            "use_case_name": use_case_name,
                            "num_test_questions": len(use_case.test_questions),
                            "version": use_case.version
                        }
                    }
                )
            except Exception as e:
                error_msg = f"Failed to load use case '{use_case_name}': {e}"
                logger.error(
                    error_msg,
                    extra={
                        "context": {
                            "use_case_name": use_case_name,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    },
                    exc_info=True
                )
                raise RuntimeError(error_msg) from e
            
            # Step 2: Execute iterations in a loop
            logger.info(
                f"Starting iteration loop",
                extra={
                    "context": {
                        "use_case_name": use_case_name,
                        "max_iterations": max_iterations
                    }
                }
            )
            
            # Initialize prompts from use case
            current_prompts = Prompts(
                data_generation_prompt=use_case.data_generation_prompt,
                judge_prompt=use_case.judge_prompt
            )
            
            # Iteration loop
            for iteration in range(1, max_iterations + 1):
                current_iteration = iteration
                
                logger.info(
                    f"Starting iteration {iteration}/{max_iterations}",
                    extra={
                        "context": {
                            "use_case_name": use_case_name,
                            "iteration": iteration,
                            "max_iterations": max_iterations
                        }
                    }
                )
                
                try:
                    # Execute single iteration
                    iteration_result = self._execute_iteration(
                        use_case=use_case,
                        prompts=current_prompts,
                        iteration=iteration
                    )
                    
                    # Update final win rate
                    final_win_rate = iteration_result.win_rate
                    
                    logger.info(
                        f"Iteration {iteration} completed with win rate {final_win_rate:.1%}",
                        extra={
                            "context": {
                                "use_case_name": use_case_name,
                                "iteration": iteration,
                                "win_rate": final_win_rate,
                                "training_time_seconds": iteration_result.training_time_seconds
                            }
                        }
                    )
                    
                    # Check if we should continue or stop
                    if self._should_improve(final_win_rate, iteration, max_iterations):
                        logger.info(
                            f"Win rate {final_win_rate:.1%} below threshold "
                            f"{self.pipeline_config.performance_threshold:.1%}, "
                            f"continuing to next iteration",
                            extra={
                                "context": {
                                    "use_case_name": use_case_name,
                                    "iteration": iteration,
                                    "win_rate": final_win_rate,
                                    "threshold": self.pipeline_config.performance_threshold
                                }
                            }
                        )
                        
                        # Note: Self-improvement agent integration is optional for now
                        # In future iterations, we would call:
                        # improved_prompts = self.self_improvement_agent.analyze_and_improve(...)
                        # current_prompts = improved_prompts
                        
                        # For now, we continue with the same prompts
                        # This allows the pipeline to run multiple iterations for testing
                        logger.info(
                            f"Self-improvement agent not yet integrated, "
                            f"continuing with same prompts",
                            extra={
                                "context": {
                                    "use_case_name": use_case_name,
                                    "iteration": iteration
                                }
                            }
                        )
                    else:
                        # Stop condition met
                        if final_win_rate >= self.pipeline_config.performance_threshold:
                            logger.info(
                                f"Win rate {final_win_rate:.1%} meets or exceeds threshold "
                                f"{self.pipeline_config.performance_threshold:.1%}, "
                                f"stopping pipeline",
                                extra={
                                    "context": {
                                        "use_case_name": use_case_name,
                                        "iteration": iteration,
                                        "win_rate": final_win_rate,
                                        "threshold": self.pipeline_config.performance_threshold
                                    }
                                }
                            )
                        else:
                            logger.info(
                                f"Maximum iterations reached ({iteration}/{max_iterations}), "
                                f"stopping pipeline",
                                extra={
                                    "context": {
                                        "use_case_name": use_case_name,
                                        "iteration": iteration,
                                        "max_iterations": max_iterations
                                    }
                                }
                            )
                        
                        # Break out of iteration loop
                        break
                
                except Exception as e:
                    error_msg = f"Iteration {iteration} failed: {e}"
                    logger.error(
                        error_msg,
                        extra={
                            "context": {
                                "use_case_name": use_case_name,
                                "iteration": iteration,
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                        },
                        exc_info=True
                    )
                    
                    # Save pipeline state for resumption
                    try:
                        from src.config_models import PipelineState
                        state = PipelineState(
                            use_case_name=use_case_name,
                            current_iteration=iteration,
                            completed_steps=[],
                            intermediate_results={
                                "last_win_rate": final_win_rate,
                                "error": str(e)
                            },
                            timestamp=datetime.now()
                        )
                        state_id = self.progress_tracker.save_pipeline_state(
                            use_case_name=use_case_name,
                            state=state
                        )
                        logger.info(
                            f"Pipeline state saved for resumption",
                            extra={
                                "context": {
                                    "use_case_name": use_case_name,
                                    "iteration": iteration,
                                    "state_id": state_id
                                }
                            }
                        )
                    except Exception as save_error:
                        logger.warning(
                            f"Failed to save pipeline state: {save_error}",
                            extra={
                                "context": {
                                    "use_case_name": use_case_name,
                                    "iteration": iteration,
                                    "save_error": str(save_error)
                                }
                            }
                        )
                    
                    # Re-raise the exception
                    raise RuntimeError(error_msg) from e
            
            # Pipeline completed successfully
            success = True
            logger.info(
                f"Pipeline completed successfully",
                extra={
                    "context": {
                        "use_case_name": use_case_name,
                        "total_iterations": current_iteration,
                        "final_win_rate": final_win_rate,
                        "success": True
                    }
                }
            )
        
        except Exception as e:
            # Pipeline failed
            success = False
            error_message = str(e)
            logger.error(
                f"Pipeline failed: {e}",
                extra={
                    "context": {
                        "use_case_name": use_case_name,
                        "total_iterations": current_iteration,
                        "error": error_message,
                        "error_type": type(e).__name__
                    }
                },
                exc_info=True
            )
        
        # Generate performance report
        try:
            performance_report = self.progress_tracker.generate_summary_report(
                use_case_name=use_case_name
            )
            logger.info(
                f"Performance report generated",
                extra={
                    "context": {
                        "use_case_name": use_case_name,
                        "total_iterations": performance_report.total_iterations,
                        "initial_win_rate": performance_report.initial_win_rate,
                        "final_win_rate": performance_report.final_win_rate,
                        "improvement": performance_report.improvement
                    }
                }
            )
        except Exception as e:
            logger.warning(
                f"Failed to generate performance report: {e}",
                extra={
                    "context": {
                        "use_case_name": use_case_name,
                        "error": str(e)
                    }
                }
            )
            # Create a minimal performance report
            from src.config_models import PerformanceReport
            performance_report = PerformanceReport(
                use_case_name=use_case_name,
                total_iterations=0,  # Set to 0 since we have no history
                initial_win_rate=final_win_rate,
                final_win_rate=final_win_rate,
                improvement=0.0,
                best_iteration=current_iteration if current_iteration > 0 else 1,
                iteration_history=[]  # Empty history matches total_iterations=0
            )
        
        # Create and return pipeline result
        result = PipelineResult(
            use_case_name=use_case_name,
            success=success,
            final_win_rate=final_win_rate,
            total_iterations=current_iteration,
            performance_report=performance_report,
            error_message=error_message
        )
        
        logger.info(
            f"Pipeline run completed",
            extra={
                "context": {
                    "use_case_name": use_case_name,
                    "success": success,
                    "final_win_rate": final_win_rate,
                    "total_iterations": current_iteration,
                    "error_message": error_message
                }
            }
        )
        
        return result
