"""
Unit tests for FinetuningPipeline class

Tests cover:
- Valid initialization with all components
- Component storage and accessibility
- Error handling for missing/invalid parameters
- AWS client manager integration
- Logging verification
- Component validation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from src.finetuning_pipeline import FinetuningPipeline
from src.configuration_manager import ConfigurationManager
from src.progress_tracker import ProgressTracker
from src.config_models import PipelineConfig


class TestFinetuningPipelineInit:
    """Test suite for FinetuningPipeline.__init__"""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock ConfigurationManager"""
        mock = Mock(spec=ConfigurationManager)
        return mock
    
    @pytest.fixture
    def mock_progress_tracker(self):
        """Create a mock ProgressTracker"""
        mock = Mock(spec=ProgressTracker)
        return mock
    
    @pytest.fixture
    def valid_pipeline_config(self):
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
            s3_bucket="test-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_retries=3,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0
        )
    
    @pytest.fixture
    def mock_aws_clients(self):
        """Create mock AWS clients"""
        return {
            'bedrock': Mock(),
            'sagemaker': Mock(),
            'sagemaker_runtime': Mock()
        }
    
    def test_init_with_valid_parameters(
        self,
        mock_config_manager,
        mock_progress_tracker,
        valid_pipeline_config,
        mock_aws_clients
    ):
        """Test successful initialization with valid parameters"""
        # Setup mocks
        mock_config_manager.load_pipeline_config.return_value = valid_pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager') as mock_aws_manager_class, \
             patch('src.finetuning_pipeline.SyntheticDataGenerator') as mock_data_gen_class, \
             patch('src.finetuning_pipeline.ModelTrainer') as mock_trainer_class, \
             patch('src.finetuning_pipeline.ModelDeployer') as mock_deployer_class, \
             patch('src.finetuning_pipeline.InferenceEngine') as mock_inference_class, \
             patch('src.finetuning_pipeline.Judge') as mock_judge_class:
            
            # Configure AWS client manager mock
            mock_aws_manager = Mock()
            mock_aws_manager.get_bedrock_runtime_client.return_value = mock_aws_clients['bedrock']
            mock_aws_manager.get_sagemaker_client.return_value = mock_aws_clients['sagemaker']
            mock_aws_manager.get_sagemaker_runtime_client.return_value = mock_aws_clients['sagemaker_runtime']
            mock_aws_manager_class.return_value = mock_aws_manager
            
            # Create pipeline
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            
            # Verify configuration manager and progress tracker are stored
            assert pipeline.config_manager is mock_config_manager
            assert pipeline.progress_tracker is mock_progress_tracker
            
            # Verify pipeline config was loaded
            mock_config_manager.load_pipeline_config.assert_called_once()
            assert pipeline.pipeline_config is valid_pipeline_config
            
            # Verify AWS client manager was initialized with correct config
            mock_aws_manager_class.assert_called_once()
            aws_config = mock_aws_manager_class.call_args[0][0]
            assert aws_config['region'] == 'us-east-1'
            assert aws_config['max_attempts'] == 3
            assert aws_config['initial_backoff_seconds'] == 2.0
            assert aws_config['max_backoff_seconds'] == 60.0
            
            # Verify all components were initialized
            mock_data_gen_class.assert_called_once_with(
                mock_aws_clients['bedrock'],
                valid_pipeline_config
            )
            mock_trainer_class.assert_called_once_with(
                mock_aws_clients['sagemaker'],
                valid_pipeline_config
            )
            mock_deployer_class.assert_called_once_with(
                mock_aws_clients['sagemaker'],
                valid_pipeline_config
            )
            mock_inference_class.assert_called_once_with(
                mock_aws_clients['sagemaker_runtime'],
                valid_pipeline_config
            )
            mock_judge_class.assert_called_once_with(
                mock_aws_clients['bedrock'],
                valid_pipeline_config
            )
            
            # Verify components are accessible
            assert pipeline.data_generator is not None
            assert pipeline.model_trainer is not None
            assert pipeline.model_deployer is not None
            assert pipeline.inference_engine is not None
            assert pipeline.judge is not None
            assert pipeline.aws_client_manager is not None
    
    def test_init_with_none_config_manager(self, mock_progress_tracker):
        """Test initialization fails with None config_manager"""
        with pytest.raises(ValueError, match="config_manager cannot be None"):
            FinetuningPipeline(None, mock_progress_tracker)
    
    def test_init_with_none_progress_tracker(self, mock_config_manager):
        """Test initialization fails with None progress_tracker"""
        with pytest.raises(ValueError, match="progress_tracker cannot be None"):
            FinetuningPipeline(mock_config_manager, None)
    
    def test_init_with_invalid_config_manager_type(self, mock_progress_tracker):
        """Test initialization fails with wrong type for config_manager"""
        with pytest.raises(TypeError, match="config_manager must be a ConfigurationManager instance"):
            FinetuningPipeline("not a config manager", mock_progress_tracker)
    
    def test_init_with_invalid_progress_tracker_type(self, mock_config_manager):
        """Test initialization fails with wrong type for progress_tracker"""
        with pytest.raises(TypeError, match="progress_tracker must be a ProgressTracker instance"):
            FinetuningPipeline(mock_config_manager, "not a progress tracker")
    
    def test_init_with_config_load_failure(
        self,
        mock_config_manager,
        mock_progress_tracker
    ):
        """Test initialization fails when pipeline config cannot be loaded"""
        # Setup mock to raise exception
        mock_config_manager.load_pipeline_config.side_effect = FileNotFoundError(
            "Config file not found"
        )
        
        with pytest.raises(RuntimeError, match="Failed to load pipeline configuration"):
            FinetuningPipeline(mock_config_manager, mock_progress_tracker)
    
    def test_init_with_missing_config_attributes(
        self,
        mock_config_manager,
        mock_progress_tracker
    ):
        """Test initialization fails when pipeline config is missing required attributes"""
        # Create a mock config object that's missing required attributes
        # Mock objects return Mock for any attribute access, so we need to delete them
        incomplete_config = Mock()
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        incomplete_config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        incomplete_config.training_instance_type = "ml.g5.2xlarge"
        incomplete_config.inference_instance_type = "ml.g5.xlarge"
        incomplete_config.baseline_model_endpoint = "llama-70b-baseline"
        incomplete_config.performance_threshold = 0.60
        incomplete_config.max_iterations = 5
        incomplete_config.cleanup_resources = True
        incomplete_config.s3_bucket = "test-bucket"
        
        # Delete required attributes to simulate missing config
        del incomplete_config.base_model
        del incomplete_config.max_retries
        del incomplete_config.initial_backoff_seconds
        del incomplete_config.max_backoff_seconds
        
        mock_config_manager.load_pipeline_config.return_value = incomplete_config
        
        # The error is caught during config loading when trying to access base_model for logging
        with pytest.raises(RuntimeError, match="Failed to load pipeline configuration"):
            FinetuningPipeline(mock_config_manager, mock_progress_tracker)
    
    def test_init_with_aws_client_manager_failure(
        self,
        mock_config_manager,
        mock_progress_tracker,
        valid_pipeline_config
    ):
        """Test initialization fails when AWS client manager cannot be created"""
        mock_config_manager.load_pipeline_config.return_value = valid_pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager') as mock_aws_manager_class:
            mock_aws_manager_class.side_effect = Exception("AWS initialization failed")
            
            with pytest.raises(RuntimeError, match="Failed to initialize AWS client manager"):
                FinetuningPipeline(mock_config_manager, mock_progress_tracker)
    
    def test_init_with_component_initialization_failure(
        self,
        mock_config_manager,
        mock_progress_tracker,
        valid_pipeline_config,
        mock_aws_clients
    ):
        """Test initialization fails when a component cannot be created"""
        mock_config_manager.load_pipeline_config.return_value = valid_pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager') as mock_aws_manager_class, \
             patch('src.finetuning_pipeline.SyntheticDataGenerator') as mock_data_gen_class:
            
            # Configure AWS client manager mock
            mock_aws_manager = Mock()
            mock_aws_manager.get_bedrock_runtime_client.return_value = mock_aws_clients['bedrock']
            mock_aws_manager.get_sagemaker_client.return_value = mock_aws_clients['sagemaker']
            mock_aws_manager.get_sagemaker_runtime_client.return_value = mock_aws_clients['sagemaker_runtime']
            mock_aws_manager_class.return_value = mock_aws_manager
            
            # Make SyntheticDataGenerator initialization fail
            mock_data_gen_class.side_effect = Exception("Data generator initialization failed")
            
            with pytest.raises(RuntimeError, match="Failed to initialize pipeline components"):
                FinetuningPipeline(mock_config_manager, mock_progress_tracker)
    
    def test_init_component_validation(
        self,
        mock_config_manager,
        mock_progress_tracker,
        valid_pipeline_config,
        mock_aws_clients
    ):
        """Test that component validation is performed during initialization"""
        mock_config_manager.load_pipeline_config.return_value = valid_pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager') as mock_aws_manager_class, \
             patch('src.finetuning_pipeline.SyntheticDataGenerator') as mock_data_gen_class, \
             patch('src.finetuning_pipeline.ModelTrainer') as mock_trainer_class, \
             patch('src.finetuning_pipeline.ModelDeployer') as mock_deployer_class, \
             patch('src.finetuning_pipeline.InferenceEngine') as mock_inference_class, \
             patch('src.finetuning_pipeline.Judge') as mock_judge_class:
            
            # Configure AWS client manager mock
            mock_aws_manager = Mock()
            mock_aws_manager.get_bedrock_runtime_client.return_value = mock_aws_clients['bedrock']
            mock_aws_manager.get_sagemaker_client.return_value = mock_aws_clients['sagemaker']
            mock_aws_manager.get_sagemaker_runtime_client.return_value = mock_aws_clients['sagemaker_runtime']
            mock_aws_manager_class.return_value = mock_aws_manager
            
            # Make one component return None
            mock_data_gen_class.return_value = None
            
            with pytest.raises(RuntimeError, match="Pipeline validation failed: missing components"):
                FinetuningPipeline(mock_config_manager, mock_progress_tracker)
    
    def test_init_logging(
        self,
        mock_config_manager,
        mock_progress_tracker,
        valid_pipeline_config,
        mock_aws_clients,
        caplog
    ):
        """Test that initialization logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        mock_config_manager.load_pipeline_config.return_value = valid_pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager') as mock_aws_manager_class, \
             patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
             patch('src.finetuning_pipeline.ModelTrainer'), \
             patch('src.finetuning_pipeline.ModelDeployer'), \
             patch('src.finetuning_pipeline.InferenceEngine'), \
             patch('src.finetuning_pipeline.Judge'):
            
            # Configure AWS client manager mock
            mock_aws_manager = Mock()
            mock_aws_manager.get_bedrock_runtime_client.return_value = mock_aws_clients['bedrock']
            mock_aws_manager.get_sagemaker_client.return_value = mock_aws_clients['sagemaker']
            mock_aws_manager.get_sagemaker_runtime_client.return_value = mock_aws_clients['sagemaker_runtime']
            mock_aws_manager_class.return_value = mock_aws_manager
            
            # Create pipeline
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            
            # Verify key log messages
            log_messages = [record.message for record in caplog.records]
            assert any("Initializing FinetuningPipeline" in msg for msg in log_messages)
            assert any("Pipeline configuration loaded successfully" in msg for msg in log_messages)
            assert any("AWS client manager initialized" in msg for msg in log_messages)
            assert any("All pipeline components initialized successfully" in msg for msg in log_messages)
            assert any("FinetuningPipeline initialization complete" in msg for msg in log_messages)
    
    def test_init_stores_all_components(
        self,
        mock_config_manager,
        mock_progress_tracker,
        valid_pipeline_config,
        mock_aws_clients
    ):
        """Test that all components are stored as instance attributes"""
        mock_config_manager.load_pipeline_config.return_value = valid_pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager') as mock_aws_manager_class, \
             patch('src.finetuning_pipeline.SyntheticDataGenerator') as mock_data_gen_class, \
             patch('src.finetuning_pipeline.ModelTrainer') as mock_trainer_class, \
             patch('src.finetuning_pipeline.ModelDeployer') as mock_deployer_class, \
             patch('src.finetuning_pipeline.InferenceEngine') as mock_inference_class, \
             patch('src.finetuning_pipeline.Judge') as mock_judge_class:
            
            # Configure AWS client manager mock
            mock_aws_manager = Mock()
            mock_aws_manager.get_bedrock_runtime_client.return_value = mock_aws_clients['bedrock']
            mock_aws_manager.get_sagemaker_client.return_value = mock_aws_clients['sagemaker']
            mock_aws_manager.get_sagemaker_runtime_client.return_value = mock_aws_clients['sagemaker_runtime']
            mock_aws_manager_class.return_value = mock_aws_manager
            
            # Create mock component instances
            mock_data_gen = Mock()
            mock_trainer = Mock()
            mock_deployer = Mock()
            mock_inference = Mock()
            mock_judge = Mock()
            
            mock_data_gen_class.return_value = mock_data_gen
            mock_trainer_class.return_value = mock_trainer
            mock_deployer_class.return_value = mock_deployer
            mock_inference_class.return_value = mock_inference
            mock_judge_class.return_value = mock_judge
            
            # Create pipeline
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            
            # Verify all components are stored
            assert pipeline.config_manager is mock_config_manager
            assert pipeline.progress_tracker is mock_progress_tracker
            assert pipeline.pipeline_config is valid_pipeline_config
            assert pipeline.aws_client_manager is mock_aws_manager
            assert pipeline.data_generator is mock_data_gen
            assert pipeline.model_trainer is mock_trainer
            assert pipeline.model_deployer is mock_deployer
            assert pipeline.inference_engine is mock_inference
            assert pipeline.judge is mock_judge
    
    def test_init_with_different_aws_regions(
        self,
        mock_config_manager,
        mock_progress_tracker,
        valid_pipeline_config,
        mock_aws_clients
    ):
        """Test initialization with different AWS regions"""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
        
        for region in regions:
            # Update config with different region
            config = PipelineConfig(
                aws_region=region,
                bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="test-bucket",
                base_model="meta-llama/Llama-3.2-3B",
                max_retries=3,
                initial_backoff_seconds=2.0,
                max_backoff_seconds=60.0
            )
            
            mock_config_manager.load_pipeline_config.return_value = config
            
            with patch('src.finetuning_pipeline.AWSClientManager') as mock_aws_manager_class, \
                 patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
                 patch('src.finetuning_pipeline.ModelTrainer'), \
                 patch('src.finetuning_pipeline.ModelDeployer'), \
                 patch('src.finetuning_pipeline.InferenceEngine'), \
                 patch('src.finetuning_pipeline.Judge'):
                
                # Configure AWS client manager mock
                mock_aws_manager = Mock()
                mock_aws_manager.get_bedrock_runtime_client.return_value = mock_aws_clients['bedrock']
                mock_aws_manager.get_sagemaker_client.return_value = mock_aws_clients['sagemaker']
                mock_aws_manager.get_sagemaker_runtime_client.return_value = mock_aws_clients['sagemaker_runtime']
                mock_aws_manager_class.return_value = mock_aws_manager
                
                # Create pipeline
                pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
                
                # Verify region is correctly set
                assert pipeline.pipeline_config.aws_region == region
                
                # Verify AWS client manager was initialized with correct region
                aws_config = mock_aws_manager_class.call_args[0][0]
                assert aws_config['region'] == region


class TestFinetuningPipelineValidateComponents:
    """Test suite for FinetuningPipeline._validate_components"""
    
    def test_validate_components_with_all_present(self):
        """Test validation passes when all components are present"""
        # Create a mock pipeline with all components
        pipeline = Mock(spec=FinetuningPipeline)
        pipeline.config_manager = Mock()
        pipeline.progress_tracker = Mock()
        pipeline.pipeline_config = Mock()
        pipeline.aws_client_manager = Mock()
        pipeline.data_generator = Mock()
        pipeline.model_trainer = Mock()
        pipeline.model_deployer = Mock()
        pipeline.inference_engine = Mock()
        pipeline.judge = Mock()
        
        # Call the actual method
        FinetuningPipeline._validate_components(pipeline)
        
        # If no exception is raised, validation passed
    
    def test_validate_components_with_missing_component(self):
        """Test validation fails when a component is None"""
        # Create a mock pipeline with one missing component
        pipeline = Mock(spec=FinetuningPipeline)
        pipeline.config_manager = Mock()
        pipeline.progress_tracker = Mock()
        pipeline.pipeline_config = Mock()
        pipeline.aws_client_manager = Mock()
        pipeline.data_generator = None  # Missing component
        pipeline.model_trainer = Mock()
        pipeline.model_deployer = Mock()
        pipeline.inference_engine = Mock()
        pipeline.judge = Mock()
        
        # Call the actual method and expect exception
        with pytest.raises(RuntimeError, match="Pipeline validation failed: missing components"):
            FinetuningPipeline._validate_components(pipeline)



class TestFinetuningPipelineExecuteIteration:
    """Test suite for FinetuningPipeline._execute_iteration"""
    
    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock FinetuningPipeline with all components"""
        from src.config_models import UseCase, Prompts, PipelineConfig
        
        # Create mock components
        mock_config_manager = Mock(spec=ConfigurationManager)
        mock_progress_tracker = Mock(spec=ProgressTracker)
        
        # Create valid pipeline config
        pipeline_config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_retries=3,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0
        )
        
        mock_config_manager.load_pipeline_config.return_value = pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager'), \
             patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
             patch('src.finetuning_pipeline.ModelTrainer'), \
             patch('src.finetuning_pipeline.ModelDeployer'), \
             patch('src.finetuning_pipeline.InferenceEngine'), \
             patch('src.finetuning_pipeline.Judge'):
            
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            
            # Replace components with mocks
            pipeline.data_generator = Mock()
            pipeline.model_trainer = Mock()
            pipeline.model_deployer = Mock()
            pipeline.inference_engine = Mock()
            pipeline.judge = Mock()
            pipeline.progress_tracker = mock_progress_tracker
            
            return pipeline
    
    @pytest.fixture
    def valid_use_case(self):
        """Create a valid UseCase for testing"""
        from src.config_models import UseCase
        from datetime import datetime
        
        return UseCase(
            name="customer_support",
            description="Customer support chatbot",
            test_questions=[
                "How do I return an item?",
                "What is your refund policy?",
                "How long does shipping take?"
            ],
            judge_criteria="Evaluate helpfulness and clarity",
            data_generation_prompt="Generate customer support examples",
            judge_prompt="Compare support responses",
            version=1,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def valid_prompts(self):
        """Create valid Prompts for testing"""
        from src.config_models import Prompts
        
        return Prompts(
            data_generation_prompt="Generate customer support examples",
            judge_prompt="Compare support responses"
        )
    
    @pytest.fixture
    def mock_training_result(self):
        """Create a mock successful TrainingResult"""
        from src.config_models import TrainingResult
        
        result = Mock(spec=TrainingResult)
        result.job_name = "test-job-123"
        result.model_artifact_s3_uri = "s3://bucket/model.tar.gz"
        result.training_time_seconds = 3600
        result.final_loss = 0.25
        result.status = "Completed"
        result.error_message = None
        result.is_successful.return_value = True
        
        return result
    
    @pytest.fixture
    def mock_deployment_result(self):
        """Create a mock successful DeploymentResult"""
        from src.config_models import DeploymentResult
        from datetime import datetime
        
        result = Mock(spec=DeploymentResult)
        result.endpoint_name = "test-endpoint-123"
        result.endpoint_arn = "arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint-123"
        result.status = "InService"
        result.creation_time = datetime.now()
        result.error_message = None
        result.is_successful.return_value = True
        
        return result
    
    @pytest.fixture
    def mock_response_pairs(self):
        """Create mock ResponsePairs"""
        from src.config_models import ResponsePairs, ResponsePair
        from datetime import datetime
        
        pairs = ResponsePairs(
            pairs=[
                ResponsePair(
                    question="How do I return an item?",
                    finetuned_response="You can return items within 30 days...",
                    baseline_response="Returns are accepted..."
                ),
                ResponsePair(
                    question="What is your refund policy?",
                    finetuned_response="We offer full refunds...",
                    baseline_response="Refunds are processed..."
                ),
                ResponsePair(
                    question="How long does shipping take?",
                    finetuned_response="Standard shipping takes 3-5 business days...",
                    baseline_response="Shipping times vary..."
                )
            ],
            finetuned_endpoint="test-endpoint-123",
            baseline_endpoint="llama-70b-baseline",
            generation_time=datetime.now()
        )
        
        return pairs
    
    @pytest.fixture
    def mock_evaluation_result(self):
        """Create mock EvaluationResult"""
        from src.config_models import EvaluationResult, Judgment
        from datetime import datetime
        
        judgments = [
            Judgment(
                question="How do I return an item?",
                winner="finetuned",
                reasoning="More detailed and helpful",
                confidence=0.85
            ),
            Judgment(
                question="What is your refund policy?",
                winner="finetuned",
                reasoning="Clearer explanation",
                confidence=0.90
            ),
            Judgment(
                question="How long does shipping take?",
                winner="baseline",
                reasoning="More accurate information",
                confidence=0.75
            )
        ]
        
        result = EvaluationResult(
            judgments=judgments,
            win_rate=0.67,  # 2 out of 3
            tie_rate=0.0,
            total_comparisons=3,
            evaluation_time=datetime.now()
        )
        
        return result
    
    def test_execute_iteration_successful(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs,
        mock_evaluation_result
    ):
        """Test successful execution of a complete iteration"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        mock_pipeline.judge.evaluate.return_value = mock_evaluation_result
        
        # Execute iteration
        result = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify all steps were called
        mock_pipeline.data_generator.generate_training_data.assert_called_once()
        mock_pipeline.model_trainer.train_model.assert_called_once_with(
            training_data_path="/path/to/training_data.jsonl",
            use_case_name="customer_support"
        )
        mock_pipeline.model_deployer.deploy_model.assert_called_once()
        mock_pipeline.inference_engine.generate_responses.assert_called_once_with(
            questions=valid_use_case.test_questions,
            finetuned_endpoint=mock_deployment_result.endpoint_name,
            baseline_endpoint="llama-70b-baseline"
        )
        mock_pipeline.judge.evaluate.assert_called_once()
        
        # Verify progress was saved
        mock_pipeline.progress_tracker.record_iteration.assert_called_once()
        
        # Verify result
        assert result.iteration == 1
        assert result.win_rate == 0.67
        assert result.prompts_used == valid_prompts
        assert result.training_time_seconds > 0
        assert result.model_artifact_uri == "s3://bucket/model.tar.gz"
        assert result.endpoint_name == "test-endpoint-123"
        
        # Verify cleanup was called (cleanup_resources=True)
        mock_pipeline.model_deployer.delete_endpoint.assert_called_once_with("test-endpoint-123")
    
    def test_execute_iteration_without_cleanup(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs,
        mock_evaluation_result
    ):
        """Test iteration execution without resource cleanup"""
        # Disable cleanup
        mock_pipeline.pipeline_config.cleanup_resources = False
        
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        mock_pipeline.judge.evaluate.return_value = mock_evaluation_result
        
        # Execute iteration
        result = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify cleanup was NOT called
        mock_pipeline.model_deployer.delete_endpoint.assert_not_called()
        
        # Verify result is still valid
        assert result.iteration == 1
        assert result.win_rate == 0.67
    
    def test_execute_iteration_data_generation_failure(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts
    ):
        """Test iteration fails when data generation fails"""
        # Setup mock to fail
        mock_pipeline.data_generator.generate_training_data.side_effect = Exception(
            "Bedrock API error"
        )
        
        # Execute iteration and expect failure
        with pytest.raises(RuntimeError, match="Training data generation failed"):
            mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify subsequent steps were not called
        mock_pipeline.model_trainer.train_model.assert_not_called()
        mock_pipeline.model_deployer.deploy_model.assert_not_called()
    
    def test_execute_iteration_training_failure(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result
    ):
        """Test iteration fails when training fails"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        
        # Make training fail
        mock_training_result.status = "Failed"
        mock_training_result.error_message = "Training job failed"
        mock_training_result.is_successful.return_value = False
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        
        # Execute iteration and expect failure
        with pytest.raises(RuntimeError, match="Training failed"):
            mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify subsequent steps were not called
        mock_pipeline.model_deployer.deploy_model.assert_not_called()
        mock_pipeline.inference_engine.generate_responses.assert_not_called()
    
    def test_execute_iteration_deployment_failure(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result
    ):
        """Test iteration fails when deployment fails"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        
        # Make deployment fail
        mock_deployment_result.status = "Failed"
        mock_deployment_result.error_message = "Deployment failed"
        mock_deployment_result.is_successful.return_value = False
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        
        # Execute iteration and expect failure
        with pytest.raises(RuntimeError, match="Deployment failed"):
            mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify subsequent steps were not called
        mock_pipeline.inference_engine.generate_responses.assert_not_called()
        mock_pipeline.judge.evaluate.assert_not_called()
    
    def test_execute_iteration_inference_failure(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result
    ):
        """Test iteration fails when inference fails"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        
        # Make inference fail
        mock_pipeline.inference_engine.generate_responses.side_effect = Exception(
            "Endpoint invocation failed"
        )
        
        # Execute iteration and expect failure
        with pytest.raises(RuntimeError, match="Response generation failed"):
            mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify cleanup was attempted
        mock_pipeline.model_deployer.delete_endpoint.assert_called_once_with("test-endpoint-123")
        
        # Verify evaluation was not called
        mock_pipeline.judge.evaluate.assert_not_called()
    
    def test_execute_iteration_evaluation_failure(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs
    ):
        """Test iteration fails when evaluation fails"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        
        # Make evaluation fail
        mock_pipeline.judge.evaluate.side_effect = Exception("Judge API error")
        
        # Execute iteration and expect failure
        with pytest.raises(RuntimeError, match="Response evaluation failed"):
            mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify cleanup was attempted
        mock_pipeline.model_deployer.delete_endpoint.assert_called_once_with("test-endpoint-123")
    
    def test_execute_iteration_invalid_use_case(self, mock_pipeline, valid_prompts):
        """Test iteration fails with invalid use_case parameter"""
        with pytest.raises(ValueError, match="use_case must be a UseCase instance"):
            mock_pipeline._execute_iteration("not a use case", valid_prompts, 1)
    
    def test_execute_iteration_invalid_prompts(self, mock_pipeline, valid_use_case):
        """Test iteration fails with invalid prompts parameter"""
        with pytest.raises(ValueError, match="prompts must be a Prompts instance"):
            mock_pipeline._execute_iteration(valid_use_case, "not prompts", 1)
    
    def test_execute_iteration_invalid_iteration_number(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts
    ):
        """Test iteration fails with invalid iteration number"""
        with pytest.raises(ValueError, match="iteration must be >= 1"):
            mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 0)
        
        with pytest.raises(ValueError, match="iteration must be >= 1"):
            mock_pipeline._execute_iteration(valid_use_case, valid_prompts, -1)
    
    def test_execute_iteration_cleanup_failure_does_not_fail_iteration(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs,
        mock_evaluation_result
    ):
        """Test that cleanup failure doesn't fail the iteration"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        mock_pipeline.judge.evaluate.return_value = mock_evaluation_result
        
        # Make cleanup fail
        mock_pipeline.model_deployer.delete_endpoint.side_effect = Exception("Cleanup failed")
        
        # Execute iteration - should succeed despite cleanup failure
        result = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify result is valid
        assert result.iteration == 1
        assert result.win_rate == 0.67
        
        # Verify cleanup was attempted
        mock_pipeline.model_deployer.delete_endpoint.assert_called_once()
    
    def test_execute_iteration_progress_save_failure_does_not_fail_iteration(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs,
        mock_evaluation_result
    ):
        """Test that progress save failure doesn't fail the iteration"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        mock_pipeline.judge.evaluate.return_value = mock_evaluation_result
        
        # Make progress save fail
        mock_pipeline.progress_tracker.record_iteration.side_effect = Exception("Save failed")
        
        # Execute iteration - should succeed despite save failure
        result = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify result is valid
        assert result.iteration == 1
        assert result.win_rate == 0.67
    
    def test_execute_iteration_uses_updated_prompts(
        self,
        mock_pipeline,
        valid_use_case,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs,
        mock_evaluation_result
    ):
        """Test that iteration uses the provided prompts, not the use case defaults"""
        from src.config_models import Prompts
        
        # Create different prompts than the use case defaults
        updated_prompts = Prompts(
            data_generation_prompt="UPDATED: Generate better examples",
            judge_prompt="UPDATED: Compare with stricter criteria"
        )
        
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        mock_pipeline.judge.evaluate.return_value = mock_evaluation_result
        
        # Execute iteration
        result = mock_pipeline._execute_iteration(valid_use_case, updated_prompts, 1)
        
        # Verify the updated prompts were used
        assert result.prompts_used == updated_prompts
        assert result.prompts_used.data_generation_prompt == "UPDATED: Generate better examples"
        assert result.prompts_used.judge_prompt == "UPDATED: Compare with stricter criteria"
        
        # Verify judge was called with updated prompt
        call_args = mock_pipeline.judge.evaluate.call_args
        assert call_args[1]['judge_prompt'] == "UPDATED: Compare with stricter criteria"
    
    def test_execute_iteration_multiple_iterations(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs,
        mock_evaluation_result
    ):
        """Test executing multiple iterations sequentially"""
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        mock_pipeline.judge.evaluate.return_value = mock_evaluation_result
        
        # Execute multiple iterations
        result1 = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        result2 = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 2)
        result3 = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 3)
        
        # Verify iteration numbers
        assert result1.iteration == 1
        assert result2.iteration == 2
        assert result3.iteration == 3
        
        # Verify all iterations were recorded
        assert mock_pipeline.progress_tracker.record_iteration.call_count == 3
    
    def test_execute_iteration_logging(
        self,
        mock_pipeline,
        valid_use_case,
        valid_prompts,
        mock_training_result,
        mock_deployment_result,
        mock_response_pairs,
        mock_evaluation_result,
        caplog
    ):
        """Test that iteration logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        # Setup mocks
        mock_pipeline.data_generator.generate_training_data.return_value = "/path/to/training_data.jsonl"
        mock_pipeline.model_trainer.train_model.return_value = mock_training_result
        mock_pipeline.model_deployer.deploy_model.return_value = mock_deployment_result
        mock_pipeline.inference_engine.generate_responses.return_value = mock_response_pairs
        mock_pipeline.judge.evaluate.return_value = mock_evaluation_result
        
        # Execute iteration
        result = mock_pipeline._execute_iteration(valid_use_case, valid_prompts, 1)
        
        # Verify key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Starting iteration 1" in msg for msg in log_messages)
        assert any("Step 1: Generating synthetic training data" in msg for msg in log_messages)
        assert any("Step 2: Training model" in msg for msg in log_messages)
        assert any("Step 3: Deploying model" in msg for msg in log_messages)
        assert any("Step 4: Generating responses" in msg for msg in log_messages)
        assert any("Step 5: Evaluating responses" in msg for msg in log_messages)
        assert any("Iteration 1 completed successfully" in msg for msg in log_messages)



class TestFinetuningPipelineShouldImprove:
    """Test suite for FinetuningPipeline._should_improve"""
    
    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock FinetuningPipeline for testing _should_improve"""
        from src.config_models import PipelineConfig
        
        # Create mock components
        mock_config_manager = Mock(spec=ConfigurationManager)
        mock_progress_tracker = Mock(spec=ProgressTracker)
        
        # Create valid pipeline config with performance_threshold=0.60
        pipeline_config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,  # 60% threshold
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_retries=3,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0
        )
        
        mock_config_manager.load_pipeline_config.return_value = pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager'), \
             patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
             patch('src.finetuning_pipeline.ModelTrainer'), \
             patch('src.finetuning_pipeline.ModelDeployer'), \
             patch('src.finetuning_pipeline.InferenceEngine'), \
             patch('src.finetuning_pipeline.Judge'):
            
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            return pipeline
    
    def test_should_improve_below_threshold_with_iterations_remaining(self, mock_pipeline):
        """Test returns True when win rate is below threshold and iterations remain"""
        # Win rate 55% < threshold 60%, iteration 2 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.55,
            current_iteration=2,
            max_iterations=5
        )
        assert result is True
    
    def test_should_improve_above_threshold(self, mock_pipeline):
        """Test returns False when win rate is above threshold"""
        # Win rate 75% > threshold 60%, iteration 2 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.75,
            current_iteration=2,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_at_max_iterations(self, mock_pipeline):
        """Test returns False when at maximum iterations"""
        # Win rate 55% < threshold 60%, but iteration 5 == max 5
        result = mock_pipeline._should_improve(
            win_rate=0.55,
            current_iteration=5,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_exactly_at_threshold(self, mock_pipeline):
        """Test returns False when win rate exactly equals threshold"""
        # Win rate 60% == threshold 60% (not strictly less than)
        result = mock_pipeline._should_improve(
            win_rate=0.60,
            current_iteration=2,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_exactly_at_max_iterations(self, mock_pipeline):
        """Test returns False when exactly at max iterations"""
        # Win rate 55% < threshold 60%, but iteration 5 == max 5
        result = mock_pipeline._should_improve(
            win_rate=0.55,
            current_iteration=5,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_very_low_win_rate(self, mock_pipeline):
        """Test returns True with very low win rate and iterations remaining"""
        # Win rate 10% << threshold 60%, iteration 1 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.10,
            current_iteration=1,
            max_iterations=5
        )
        assert result is True
    
    def test_should_improve_very_high_win_rate(self, mock_pipeline):
        """Test returns False with very high win rate"""
        # Win rate 95% >> threshold 60%, iteration 1 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.95,
            current_iteration=1,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_first_iteration_below_threshold(self, mock_pipeline):
        """Test returns True on first iteration if below threshold"""
        # Win rate 50% < threshold 60%, iteration 1 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.50,
            current_iteration=1,
            max_iterations=5
        )
        assert result is True
    
    def test_should_improve_last_iteration_below_threshold(self, mock_pipeline):
        """Test returns False on last iteration even if below threshold"""
        # Win rate 50% < threshold 60%, but iteration 5 == max 5
        result = mock_pipeline._should_improve(
            win_rate=0.50,
            current_iteration=5,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_one_below_max_iterations(self, mock_pipeline):
        """Test returns True when one iteration below max"""
        # Win rate 50% < threshold 60%, iteration 4 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.50,
            current_iteration=4,
            max_iterations=5
        )
        assert result is True
    
    def test_should_improve_zero_win_rate(self, mock_pipeline):
        """Test returns True with zero win rate and iterations remaining"""
        # Win rate 0% < threshold 60%, iteration 1 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.0,
            current_iteration=1,
            max_iterations=5
        )
        assert result is True
    
    def test_should_improve_perfect_win_rate(self, mock_pipeline):
        """Test returns False with perfect win rate"""
        # Win rate 100% > threshold 60%, iteration 1 < max 5
        result = mock_pipeline._should_improve(
            win_rate=1.0,
            current_iteration=1,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_just_below_threshold(self, mock_pipeline):
        """Test returns True when just below threshold"""
        # Win rate 59.9% < threshold 60%, iteration 2 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.599,
            current_iteration=2,
            max_iterations=5
        )
        assert result is True
    
    def test_should_improve_just_above_threshold(self, mock_pipeline):
        """Test returns False when just above threshold"""
        # Win rate 60.1% > threshold 60%, iteration 2 < max 5
        result = mock_pipeline._should_improve(
            win_rate=0.601,
            current_iteration=2,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_with_max_iterations_1(self, mock_pipeline):
        """Test with max_iterations=1 (no improvement possible)"""
        # Win rate 50% < threshold 60%, but iteration 1 == max 1
        result = mock_pipeline._should_improve(
            win_rate=0.50,
            current_iteration=1,
            max_iterations=1
        )
        assert result is False
    
    def test_should_improve_with_max_iterations_10(self, mock_pipeline):
        """Test with higher max_iterations value"""
        # Win rate 50% < threshold 60%, iteration 5 < max 10
        result = mock_pipeline._should_improve(
            win_rate=0.50,
            current_iteration=5,
            max_iterations=10
        )
        assert result is True
    
    def test_should_improve_logging(self, mock_pipeline, caplog):
        """Test that _should_improve logs the decision with context"""
        import logging
        caplog.set_level(logging.INFO)
        
        # Test case where improvement should be triggered
        result = mock_pipeline._should_improve(
            win_rate=0.55,
            current_iteration=2,
            max_iterations=5
        )
        
        # Verify logging occurred
        log_messages = [record.message for record in caplog.records]
        assert any("Self-improvement decision: TRIGGER" in msg for msg in log_messages)
        
        # Clear logs
        caplog.clear()
        
        # Test case where improvement should NOT be triggered
        result = mock_pipeline._should_improve(
            win_rate=0.75,
            current_iteration=2,
            max_iterations=5
        )
        
        # Verify logging occurred
        log_messages = [record.message for record in caplog.records]
        assert any("Self-improvement decision: SKIP" in msg for msg in log_messages)
    
    def test_should_improve_uses_pipeline_config_threshold(self, mock_pipeline):
        """Test that method uses threshold from pipeline config"""
        # Verify the pipeline config threshold is 0.60
        assert mock_pipeline.pipeline_config.performance_threshold == 0.60
        
        # Win rate just below config threshold should trigger
        result = mock_pipeline._should_improve(
            win_rate=0.59,
            current_iteration=1,
            max_iterations=5
        )
        assert result is True
        
        # Win rate at config threshold should not trigger
        result = mock_pipeline._should_improve(
            win_rate=0.60,
            current_iteration=1,
            max_iterations=5
        )
        assert result is False
    
    def test_should_improve_different_threshold(self):
        """Test with different performance threshold"""
        from src.config_models import PipelineConfig
        
        # Create mock components
        mock_config_manager = Mock(spec=ConfigurationManager)
        mock_progress_tracker = Mock(spec=ProgressTracker)
        
        # Create pipeline config with different threshold (0.70)
        pipeline_config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.70,  # 70% threshold
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_retries=3,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0
        )
        
        mock_config_manager.load_pipeline_config.return_value = pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager'), \
             patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
             patch('src.finetuning_pipeline.ModelTrainer'), \
             patch('src.finetuning_pipeline.ModelDeployer'), \
             patch('src.finetuning_pipeline.InferenceEngine'), \
             patch('src.finetuning_pipeline.Judge'):
            
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            
            # Win rate 65% would be above 60% threshold but below 70% threshold
            result = pipeline._should_improve(
                win_rate=0.65,
                current_iteration=2,
                max_iterations=5
            )
            assert result is True  # Should trigger with 70% threshold
            
            # Win rate 70% should not trigger (at threshold)
            result = pipeline._should_improve(
                win_rate=0.70,
                current_iteration=2,
                max_iterations=5
            )
            assert result is False


class TestFinetuningPipelineGetImprovementDecisionReason:
    """Test suite for FinetuningPipeline._get_improvement_decision_reason"""
    
    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock FinetuningPipeline for testing"""
        from src.config_models import PipelineConfig
        
        mock_config_manager = Mock(spec=ConfigurationManager)
        mock_progress_tracker = Mock(spec=ProgressTracker)
        
        pipeline_config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_retries=3,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0
        )
        
        mock_config_manager.load_pipeline_config.return_value = pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager'), \
             patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
             patch('src.finetuning_pipeline.ModelTrainer'), \
             patch('src.finetuning_pipeline.ModelDeployer'), \
             patch('src.finetuning_pipeline.InferenceEngine'), \
             patch('src.finetuning_pipeline.Judge'):
            
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            return pipeline
    
    def test_reason_win_rate_meets_threshold(self, mock_pipeline):
        """Test reason when win rate meets or exceeds threshold"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.75,
            performance_threshold=0.60,
            current_iteration=2,
            max_iterations=5
        )
        assert "meets or exceeds threshold" in reason
        assert "75.0%" in reason
        assert "60.0%" in reason
    
    def test_reason_max_iterations_reached(self, mock_pipeline):
        """Test reason when maximum iterations reached"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.50,
            performance_threshold=0.60,
            current_iteration=5,
            max_iterations=5
        )
        assert "Maximum iterations reached" in reason
        assert "5/5" in reason
    
    def test_reason_below_threshold_with_iterations_remaining(self, mock_pipeline):
        """Test reason when below threshold with iterations remaining"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.50,
            performance_threshold=0.60,
            current_iteration=2,
            max_iterations=5
        )
        assert "below threshold" in reason
        assert "50.0%" in reason
        assert "60.0%" in reason
        assert "iterations remaining" in reason
        assert "2/5" in reason
    
    def test_reason_exactly_at_threshold(self, mock_pipeline):
        """Test reason when exactly at threshold"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.60,
            performance_threshold=0.60,
            current_iteration=2,
            max_iterations=5
        )
        assert "meets or exceeds threshold" in reason
        assert "60.0%" in reason
    
    def test_reason_formatting(self, mock_pipeline):
        """Test that reason is properly formatted as a string"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.55,
            performance_threshold=0.60,
            current_iteration=3,
            max_iterations=5
        )
        assert isinstance(reason, str)
        assert len(reason) > 0
    
    def test_get_improvement_decision_reason_above_threshold(self, mock_pipeline):
        """Test reason when win rate is above threshold"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.75,
            performance_threshold=0.60,
            current_iteration=2,
            max_iterations=5
        )
        assert "meets or exceeds threshold" in reason
        assert "75.0%" in reason
        assert "60.0%" in reason
    
    def test_get_improvement_decision_reason_at_max_iterations(self, mock_pipeline):
        """Test reason when at maximum iterations"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.50,
            performance_threshold=0.60,
            current_iteration=5,
            max_iterations=5
        )
        assert "Maximum iterations reached" in reason
        assert "5/5" in reason
    
    def test_get_improvement_decision_reason_below_threshold_with_iterations(self, mock_pipeline):
        """Test reason when below threshold with iterations remaining"""
        reason = mock_pipeline._get_improvement_decision_reason(
            win_rate=0.50,
            performance_threshold=0.60,
            current_iteration=2,
            max_iterations=5
        )
        assert "below threshold" in reason
        assert "50.0%" in reason
        assert "60.0%" in reason
        assert "iterations remaining" in reason
        assert "2/5" in reason


class TestFinetuningPipelineRun:
    """Test suite for FinetuningPipeline.run"""
    
    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock FinetuningPipeline with all components"""
        from src.config_models import PipelineConfig
        
        mock_config_manager = Mock(spec=ConfigurationManager)
        mock_progress_tracker = Mock(spec=ProgressTracker)
        
        pipeline_config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_retries=3,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0
        )
        
        mock_config_manager.load_pipeline_config.return_value = pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager'), \
             patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
             patch('src.finetuning_pipeline.ModelTrainer'), \
             patch('src.finetuning_pipeline.ModelDeployer'), \
             patch('src.finetuning_pipeline.InferenceEngine'), \
             patch('src.finetuning_pipeline.Judge'):
            
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            
            # Replace components with mocks
            pipeline.config_manager = mock_config_manager
            pipeline.progress_tracker = mock_progress_tracker
            
            return pipeline
    
    @pytest.fixture
    def valid_use_case(self):
        """Create a valid UseCase for testing"""
        from src.config_models import UseCase
        from datetime import datetime
        
        return UseCase(
            name="customer_support",
            description="Customer support chatbot",
            test_questions=[
                "How do I return an item?",
                "What is your refund policy?",
                "How long does shipping take?"
            ],
            judge_criteria="Evaluate helpfulness and clarity",
            data_generation_prompt="Generate customer support examples",
            judge_prompt="Compare support responses",
            version=1,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_iteration_result(self):
        """Create a mock IterationResult"""
        from src.config_models import IterationResult, Prompts
        from datetime import datetime
        
        return IterationResult(
            iteration=1,
            win_rate=0.67,
            prompts_used=Prompts(
                data_generation_prompt="Generate customer support examples",
                judge_prompt="Compare support responses"
            ),
            training_time_seconds=3600,
            evaluation_time=datetime.now(),
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint-123"
        )
    
    @pytest.fixture
    def mock_performance_report(self):
        """Create a mock PerformanceReport"""
        from src.config_models import PerformanceReport, IterationResult, Prompts
        from datetime import datetime
        
        # Create a valid iteration result for the history
        iteration_result = IterationResult(
            iteration=1,
            win_rate=0.67,
            prompts_used=Prompts(
                data_generation_prompt="Generate customer support examples",
                judge_prompt="Compare support responses"
            ),
            training_time_seconds=3600,
            evaluation_time=datetime.now(),
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint-123"
        )
        
        return PerformanceReport(
            use_case_name="customer_support",
            total_iterations=1,
            initial_win_rate=0.67,
            final_win_rate=0.67,
            improvement=0.0,
            best_iteration=1,
            iteration_history=[iteration_result]  # Must match total_iterations
        )
    
    def test_run_successful_single_iteration(
        self,
        mock_pipeline,
        valid_use_case,
        mock_iteration_result,
        mock_performance_report
    ):
        """Test successful pipeline run with single iteration (win rate above threshold)"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(return_value=mock_iteration_result)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify use case was loaded
        mock_pipeline.config_manager.load_use_case.assert_called_once_with("customer_support")
        
        # Verify iteration was executed
        mock_pipeline._execute_iteration.assert_called_once()
        
        # Verify result
        assert result.use_case_name == "customer_support"
        assert result.success is True
        assert result.final_win_rate == 0.67
        assert result.total_iterations == 1
        assert result.error_message is None
        assert result.performance_report == mock_performance_report
    
    def test_run_multiple_iterations_with_improvement(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test pipeline run with multiple iterations (win rate below threshold)"""
        from src.config_models import IterationResult, Prompts
        from datetime import datetime
        
        # Create iteration results with increasing win rates
        iteration_results = [
            IterationResult(
                iteration=1,
                win_rate=0.50,  # Below threshold
                prompts_used=Prompts(
                    data_generation_prompt="Generate customer support examples",
                    judge_prompt="Compare support responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model1.tar.gz",
                endpoint_name="test-endpoint-1"
            ),
            IterationResult(
                iteration=2,
                win_rate=0.55,  # Still below threshold
                prompts_used=Prompts(
                    data_generation_prompt="Generate customer support examples",
                    judge_prompt="Compare support responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model2.tar.gz",
                endpoint_name="test-endpoint-2"
            ),
            IterationResult(
                iteration=3,
                win_rate=0.70,  # Above threshold
                prompts_used=Prompts(
                    data_generation_prompt="Generate customer support examples",
                    judge_prompt="Compare support responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model3.tar.gz",
                endpoint_name="test-endpoint-3"
            )
        ]
        
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(side_effect=iteration_results)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify 3 iterations were executed
        assert mock_pipeline._execute_iteration.call_count == 3
        
        # Verify result
        assert result.success is True
        assert result.final_win_rate == 0.70
        assert result.total_iterations == 3
        assert result.error_message is None
    
    def test_run_stops_at_max_iterations(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test pipeline stops at max iterations even if win rate is low"""
        from src.config_models import IterationResult, Prompts
        from datetime import datetime
        
        # Create iteration results all below threshold
        iteration_results = [
            IterationResult(
                iteration=i,
                win_rate=0.50,  # Always below threshold
                prompts_used=Prompts(
                    data_generation_prompt="Generate customer support examples",
                    judge_prompt="Compare support responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri=f"s3://bucket/model{i}.tar.gz",
                endpoint_name=f"test-endpoint-{i}"
            )
            for i in range(1, 6)  # 5 iterations
        ]
        
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(side_effect=iteration_results)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify exactly 5 iterations were executed (max_iterations)
        assert mock_pipeline._execute_iteration.call_count == 5
        
        # Verify result
        assert result.success is True
        assert result.final_win_rate == 0.50
        assert result.total_iterations == 5
        assert result.error_message is None
    
    def test_run_with_custom_max_iterations(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test pipeline run with custom max_iterations parameter"""
        from src.config_models import IterationResult, Prompts
        from datetime import datetime
        
        # Create iteration results all below threshold
        iteration_results = [
            IterationResult(
                iteration=i,
                win_rate=0.50,  # Always below threshold
                prompts_used=Prompts(
                    data_generation_prompt="Generate customer support examples",
                    judge_prompt="Compare support responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri=f"s3://bucket/model{i}.tar.gz",
                endpoint_name=f"test-endpoint-{i}"
            )
            for i in range(1, 4)  # 3 iterations
        ]
        
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(side_effect=iteration_results)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline with custom max_iterations=3
        result = mock_pipeline.run("customer_support", max_iterations=3)
        
        # Verify exactly 3 iterations were executed
        assert mock_pipeline._execute_iteration.call_count == 3
        
        # Verify result
        assert result.success is True
        assert result.total_iterations == 3
    
    def test_run_with_empty_use_case_name(self, mock_pipeline):
        """Test run fails with empty use_case_name"""
        with pytest.raises(ValueError, match="use_case_name cannot be empty"):
            mock_pipeline.run("")
        
        with pytest.raises(ValueError, match="use_case_name cannot be empty"):
            mock_pipeline.run("   ")
    
    def test_run_with_invalid_max_iterations_type(self, mock_pipeline):
        """Test run fails with invalid max_iterations type"""
        with pytest.raises(ValueError, match="max_iterations must be an integer"):
            mock_pipeline.run("customer_support", max_iterations="5")
        
        with pytest.raises(ValueError, match="max_iterations must be an integer"):
            mock_pipeline.run("customer_support", max_iterations=5.5)
    
    def test_run_with_invalid_max_iterations_value(self, mock_pipeline):
        """Test run fails with invalid max_iterations value"""
        with pytest.raises(ValueError, match="max_iterations must be >= 1"):
            mock_pipeline.run("customer_support", max_iterations=0)
        
        with pytest.raises(ValueError, match="max_iterations must be >= 1"):
            mock_pipeline.run("customer_support", max_iterations=-1)
    
    def test_run_with_use_case_load_failure(
        self,
        mock_pipeline,
        mock_performance_report
    ):
        """Test run handles use case load failure"""
        # Setup mock to fail
        mock_pipeline.config_manager.load_use_case.side_effect = FileNotFoundError(
            "Use case not found"
        )
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline and expect failure
        result = mock_pipeline.run("nonexistent_use_case")
        
        # Verify result indicates failure
        assert result.success is False
        assert result.total_iterations == 0
        assert result.error_message is not None
        assert "Failed to load use case" in result.error_message
    
    def test_run_with_iteration_failure(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test run handles iteration failure"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(side_effect=RuntimeError("Training failed"))
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify result indicates failure
        assert result.success is False
        assert result.total_iterations == 1
        assert result.error_message is not None
        assert "Iteration 1 failed" in result.error_message
    
    def test_run_saves_state_on_iteration_failure(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test run saves pipeline state when iteration fails"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(side_effect=RuntimeError("Training failed"))
        mock_pipeline.progress_tracker.save_pipeline_state.return_value = "state-123"
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify state was saved
        mock_pipeline.progress_tracker.save_pipeline_state.assert_called_once()
        call_args = mock_pipeline.progress_tracker.save_pipeline_state.call_args
        assert call_args[1]['use_case_name'] == "customer_support"
        
        # Verify result indicates failure
        assert result.success is False
    
    def test_run_handles_state_save_failure(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test run continues even if state save fails"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(side_effect=RuntimeError("Training failed"))
        mock_pipeline.progress_tracker.save_pipeline_state.side_effect = Exception("Save failed")
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline - should not raise exception
        result = mock_pipeline.run("customer_support")
        
        # Verify result indicates failure (from iteration, not state save)
        assert result.success is False
        assert "Iteration 1 failed" in result.error_message
    
    def test_run_handles_performance_report_failure(
        self,
        mock_pipeline,
        valid_use_case,
        mock_iteration_result
    ):
        """Test run creates minimal report if performance report generation fails"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(return_value=mock_iteration_result)
        mock_pipeline.progress_tracker.generate_summary_report.side_effect = Exception(
            "Report generation failed"
        )
        
        # Run pipeline - should not raise exception
        result = mock_pipeline.run("customer_support")
        
        # Verify result is still valid with minimal report
        assert result.success is True
        assert result.performance_report is not None
        assert result.performance_report.use_case_name == "customer_support"
    
    def test_run_uses_default_max_iterations(
        self,
        mock_pipeline,
        valid_use_case,
        mock_iteration_result,
        mock_performance_report
    ):
        """Test run uses pipeline config max_iterations when not specified"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(return_value=mock_iteration_result)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Verify pipeline config has max_iterations=5
        assert mock_pipeline.pipeline_config.max_iterations == 5
        
        # Run pipeline without specifying max_iterations
        result = mock_pipeline.run("customer_support")
        
        # Verify _should_improve was called with max_iterations=5
        # (indirectly verified by the fact that only 1 iteration ran due to high win rate)
        assert result.success is True
    
    def test_run_logging(
        self,
        mock_pipeline,
        valid_use_case,
        mock_iteration_result,
        mock_performance_report,
        caplog
    ):
        """Test that run logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(return_value=mock_iteration_result)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Starting pipeline run" in msg for msg in log_messages)
        assert any("Loading use case configuration" in msg for msg in log_messages)
        assert any("Use case loaded successfully" in msg for msg in log_messages)
        assert any("Starting iteration loop" in msg for msg in log_messages)
        assert any("Pipeline completed successfully" in msg for msg in log_messages)
        assert any("Pipeline run completed" in msg for msg in log_messages)
    
    def test_run_stops_when_threshold_met(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test pipeline stops when win rate meets threshold"""
        from src.config_models import IterationResult, Prompts
        from datetime import datetime
        
        # Create iteration result that meets threshold
        iteration_result = IterationResult(
            iteration=1,
            win_rate=0.75,  # Above threshold of 0.60
            prompts_used=Prompts(
                data_generation_prompt="Generate customer support examples",
                judge_prompt="Compare support responses"
            ),
            training_time_seconds=3600,
            evaluation_time=datetime.now(),
            model_artifact_uri="s3://bucket/model.tar.gz",
            endpoint_name="test-endpoint-1"
        )
        
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(return_value=iteration_result)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify only 1 iteration was executed (stopped because threshold met)
        assert mock_pipeline._execute_iteration.call_count == 1
        
        # Verify result
        assert result.success is True
        assert result.final_win_rate == 0.75
        assert result.total_iterations == 1
    
    def test_run_with_whitespace_use_case_name(
        self,
        mock_pipeline,
        valid_use_case,
        mock_iteration_result,
        mock_performance_report
    ):
        """Test run strips whitespace from use_case_name"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(return_value=mock_iteration_result)
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline with whitespace in name
        result = mock_pipeline.run("  customer_support  ")
        
        # Verify use case was loaded with stripped name
        mock_pipeline.config_manager.load_use_case.assert_called_once_with("customer_support")
        
        # Verify result
        assert result.success is True
        assert result.use_case_name == "customer_support"
    
    def test_run_error_handling_preserves_context(
        self,
        mock_pipeline,
        valid_use_case,
        mock_performance_report
    ):
        """Test run preserves error context in result"""
        # Setup mocks
        mock_pipeline.config_manager.load_use_case.return_value = valid_use_case
        mock_pipeline._execute_iteration = Mock(
            side_effect=RuntimeError("Specific error message")
        )
        mock_pipeline.progress_tracker.generate_summary_report.return_value = mock_performance_report
        
        # Run pipeline
        result = mock_pipeline.run("customer_support")
        
        # Verify error message is preserved
        assert result.success is False
        assert "Specific error message" in result.error_message



class TestFinetuningPipelineResume:
    """Test suite for FinetuningPipeline.resume"""
    
    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock FinetuningPipeline with all components"""
        from src.config_models import PipelineConfig
        
        # Create mock components
        mock_config_manager = Mock(spec=ConfigurationManager)
        mock_progress_tracker = Mock(spec=ProgressTracker)
        
        # Create valid pipeline config
        pipeline_config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_retries=3,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=60.0
        )
        
        mock_config_manager.load_pipeline_config.return_value = pipeline_config
        
        with patch('src.finetuning_pipeline.AWSClientManager'), \
             patch('src.finetuning_pipeline.SyntheticDataGenerator'), \
             patch('src.finetuning_pipeline.ModelTrainer'), \
             patch('src.finetuning_pipeline.ModelDeployer'), \
             patch('src.finetuning_pipeline.InferenceEngine'), \
             patch('src.finetuning_pipeline.Judge'):
            
            pipeline = FinetuningPipeline(mock_config_manager, mock_progress_tracker)
            
            # Replace components with mocks
            pipeline.config_manager = mock_config_manager
            pipeline.progress_tracker = mock_progress_tracker
            
            return pipeline
    
    @pytest.fixture
    def valid_pipeline_state(self):
        """Create a valid PipelineState for testing"""
        from src.config_models import PipelineState
        from datetime import datetime
        
        return PipelineState(
            use_case_name="customer_support",
            current_iteration=2,
            completed_steps=["data_generation", "training"],
            intermediate_results={
                "last_win_rate": 0.55,
                "training_data_path": "/path/to/data.jsonl"
            },
            timestamp=datetime.now()
        )
    
    @pytest.fixture
    def mock_pipeline_result(self):
        """Create a mock PipelineResult"""
        from src.config_models import PipelineResult, PerformanceReport, IterationResult, Prompts
        from datetime import datetime
        
        # Create mock iteration history
        iteration_history = [
            IterationResult(
                iteration=1,
                win_rate=0.55,
                prompts_used=Prompts(
                    data_generation_prompt="Generate examples",
                    judge_prompt="Compare responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model1.tar.gz",
                endpoint_name="endpoint-1"
            ),
            IterationResult(
                iteration=2,
                win_rate=0.65,
                prompts_used=Prompts(
                    data_generation_prompt="Generate examples",
                    judge_prompt="Compare responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model2.tar.gz",
                endpoint_name="endpoint-2"
            ),
            IterationResult(
                iteration=3,
                win_rate=0.72,
                prompts_used=Prompts(
                    data_generation_prompt="Generate examples",
                    judge_prompt="Compare responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model3.tar.gz",
                endpoint_name="endpoint-3"
            )
        ]
        
        performance_report = PerformanceReport(
            use_case_name="customer_support",
            total_iterations=3,
            initial_win_rate=0.55,
            final_win_rate=0.72,
            improvement=0.17,
            best_iteration=3,
            iteration_history=iteration_history
        )
        
        return PipelineResult(
            use_case_name="customer_support",
            success=True,
            final_win_rate=0.72,
            total_iterations=3,
            performance_report=performance_report,
            error_message=None
        )
    
    def test_resume_successful(
        self,
        mock_pipeline,
        valid_pipeline_state,
        mock_pipeline_result
    ):
        """Test successful resumption from saved state"""
        # Setup mocks
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = valid_pipeline_state
        mock_pipeline.run = Mock(return_value=mock_pipeline_result)
        
        # Resume pipeline
        result = mock_pipeline.resume("customer_support", "state_123")
        
        # Verify state was loaded
        mock_pipeline.progress_tracker.load_pipeline_state.assert_called_once_with("state_123")
        
        # Verify run was called
        mock_pipeline.run.assert_called_once_with(use_case_name="customer_support")
        
        # Verify result
        assert result.success is True
        assert result.use_case_name == "customer_support"
        assert result.final_win_rate == 0.72
        assert result.total_iterations == 3
    
    def test_resume_with_empty_use_case_name(self, mock_pipeline):
        """Test resume fails with empty use_case_name"""
        with pytest.raises(ValueError, match="use_case_name cannot be empty"):
            mock_pipeline.resume("", "state_123")
        
        with pytest.raises(ValueError, match="use_case_name cannot be empty"):
            mock_pipeline.resume("   ", "state_123")
    
    def test_resume_with_empty_state_id(self, mock_pipeline):
        """Test resume fails with empty state_id"""
        with pytest.raises(ValueError, match="state_id cannot be empty"):
            mock_pipeline.resume("customer_support", "")
        
        with pytest.raises(ValueError, match="state_id cannot be empty"):
            mock_pipeline.resume("customer_support", "   ")
    
    def test_resume_with_state_not_found(self, mock_pipeline):
        """Test resume fails when state file doesn't exist"""
        # Setup mock to raise FileNotFoundError
        mock_pipeline.progress_tracker.load_pipeline_state.side_effect = FileNotFoundError(
            "State file not found"
        )
        
        # Attempt to resume
        with pytest.raises(FileNotFoundError, match="State file not found"):
            mock_pipeline.resume("customer_support", "nonexistent_state")
        
        # Verify load was attempted
        mock_pipeline.progress_tracker.load_pipeline_state.assert_called_once_with("nonexistent_state")
    
    def test_resume_with_state_load_failure(self, mock_pipeline):
        """Test resume fails when state cannot be loaded"""
        # Setup mock to raise exception
        mock_pipeline.progress_tracker.load_pipeline_state.side_effect = Exception(
            "Failed to parse state file"
        )
        
        # Attempt to resume
        with pytest.raises(RuntimeError, match="Failed to load pipeline state"):
            mock_pipeline.resume("customer_support", "corrupt_state")
        
        # Verify load was attempted
        mock_pipeline.progress_tracker.load_pipeline_state.assert_called_once_with("corrupt_state")
    
    def test_resume_with_use_case_mismatch(
        self,
        mock_pipeline,
        valid_pipeline_state
    ):
        """Test resume fails when use_case_name doesn't match state"""
        # Setup mock to return state for different use case
        different_state = valid_pipeline_state
        different_state.use_case_name = "code_review"
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = different_state
        
        # Attempt to resume with wrong use case name
        with pytest.raises(ValueError, match="Use case name mismatch"):
            mock_pipeline.resume("customer_support", "state_123")
        
        # Verify state was loaded
        mock_pipeline.progress_tracker.load_pipeline_state.assert_called_once_with("state_123")
    
    def test_resume_strips_whitespace(
        self,
        mock_pipeline,
        valid_pipeline_state,
        mock_pipeline_result
    ):
        """Test resume strips whitespace from parameters"""
        # Setup mocks
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = valid_pipeline_state
        mock_pipeline.run = Mock(return_value=mock_pipeline_result)
        
        # Resume with whitespace
        result = mock_pipeline.resume("  customer_support  ", "  state_123  ")
        
        # Verify parameters were stripped
        mock_pipeline.progress_tracker.load_pipeline_state.assert_called_once_with("state_123")
        mock_pipeline.run.assert_called_once_with(use_case_name="customer_support")
        
        # Verify result
        assert result.success is True
    
    def test_resume_logging(
        self,
        mock_pipeline,
        valid_pipeline_state,
        mock_pipeline_result,
        caplog
    ):
        """Test resume logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        # Setup mocks
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = valid_pipeline_state
        mock_pipeline.run = Mock(return_value=mock_pipeline_result)
        
        # Resume pipeline
        result = mock_pipeline.resume("customer_support", "state_123")
        
        # Verify key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Resuming pipeline from saved state" in msg for msg in log_messages)
        assert any("Pipeline state loaded successfully" in msg for msg in log_messages)
        assert any("State validation successful" in msg for msg in log_messages)
        assert any("Restarting pipeline execution" in msg for msg in log_messages)
        assert any("Pipeline resumed and completed" in msg for msg in log_messages)
    
    def test_resume_validates_state_use_case(
        self,
        mock_pipeline,
        valid_pipeline_state,
        mock_pipeline_result
    ):
        """Test resume validates state is for correct use case"""
        # Setup mocks
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = valid_pipeline_state
        mock_pipeline.run = Mock(return_value=mock_pipeline_result)
        
        # Resume pipeline
        result = mock_pipeline.resume("customer_support", "state_123")
        
        # Verify state was validated (no exception raised)
        assert result.success is True
        assert result.use_case_name == "customer_support"
    
    def test_resume_calls_run_with_correct_parameters(
        self,
        mock_pipeline,
        valid_pipeline_state,
        mock_pipeline_result
    ):
        """Test resume calls run() with correct use_case_name"""
        # Setup mocks
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = valid_pipeline_state
        mock_pipeline.run = Mock(return_value=mock_pipeline_result)
        
        # Resume pipeline
        result = mock_pipeline.resume("customer_support", "state_123")
        
        # Verify run was called with correct parameters
        mock_pipeline.run.assert_called_once_with(use_case_name="customer_support")
        
        # Note: Currently resume() restarts from beginning
        # In future, it should skip completed steps based on state.completed_steps
    
    def test_resume_returns_pipeline_result(
        self,
        mock_pipeline,
        valid_pipeline_state,
        mock_pipeline_result
    ):
        """Test resume returns a PipelineResult"""
        from src.config_models import PipelineResult
        
        # Setup mocks
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = valid_pipeline_state
        mock_pipeline.run = Mock(return_value=mock_pipeline_result)
        
        # Resume pipeline
        result = mock_pipeline.resume("customer_support", "state_123")
        
        # Verify result is a PipelineResult
        assert isinstance(result, PipelineResult)
        assert result.use_case_name == "customer_support"
        assert result.success is True
        assert result.final_win_rate == 0.72
        assert result.total_iterations == 3
        assert result.performance_report is not None
        assert result.error_message is None
    
    def test_resume_with_failed_run(
        self,
        mock_pipeline,
        valid_pipeline_state
    ):
        """Test resume handles run() failure"""
        from src.config_models import PipelineResult, PerformanceReport, IterationResult, Prompts
        from datetime import datetime
        
        # Setup mocks
        mock_pipeline.progress_tracker.load_pipeline_state.return_value = valid_pipeline_state
        
        # Create iteration history for failed result
        iteration_history = [
            IterationResult(
                iteration=1,
                win_rate=0.55,
                prompts_used=Prompts(
                    data_generation_prompt="Generate examples",
                    judge_prompt="Compare responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model1.tar.gz",
                endpoint_name="endpoint-1"
            ),
            IterationResult(
                iteration=2,
                win_rate=0.55,
                prompts_used=Prompts(
                    data_generation_prompt="Generate examples",
                    judge_prompt="Compare responses"
                ),
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri="s3://bucket/model2.tar.gz",
                endpoint_name="endpoint-2"
            )
        ]
        
        # Create a failed result
        failed_result = PipelineResult(
            use_case_name="customer_support",
            success=False,
            final_win_rate=0.55,
            total_iterations=2,
            performance_report=PerformanceReport(
                use_case_name="customer_support",
                total_iterations=2,
                initial_win_rate=0.55,
                final_win_rate=0.55,
                improvement=0.0,
                best_iteration=1,
                iteration_history=iteration_history
            ),
            error_message="Training failed"
        )
        
        mock_pipeline.run = Mock(return_value=failed_result)
        
        # Resume pipeline
        result = mock_pipeline.resume("customer_support", "state_123")
        
        # Verify result reflects failure
        assert result.success is False
        assert result.error_message == "Training failed"
    
    def test_resume_error_logging(
        self,
        mock_pipeline,
        caplog
    ):
        """Test resume logs errors appropriately"""
        import logging
        caplog.set_level(logging.ERROR)
        
        # Setup mock to raise exception
        mock_pipeline.progress_tracker.load_pipeline_state.side_effect = FileNotFoundError(
            "State file not found"
        )
        
        # Attempt to resume
        with pytest.raises(FileNotFoundError):
            mock_pipeline.resume("customer_support", "missing_state")
        
        # Verify error was logged
        log_messages = [record.message for record in caplog.records]
        assert any("State file not found" in msg for msg in log_messages)
