"""
Unit tests for ModelTrainer class.

Tests cover:
- __init__ method with valid and invalid parameters
- SageMaker client initialization
- Configuration validation
- Error handling for missing or invalid inputs
- train_model() method with various scenarios
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.model_trainer import ModelTrainer
from src.config_models import PipelineConfig, TrainingResult


class TestModelTrainerInit:
    """Test suite for ModelTrainer.__init__ method"""
    
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
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        mock_client = Mock()
        mock_client.create_training_job = Mock(return_value={
            'TrainingJobArn': 'arn:aws:sagemaker:us-east-1:123456789012:training-job/test-job'
        })
        mock_client.describe_training_job = Mock(return_value={
            'TrainingJobStatus': 'Completed',
            'ModelArtifacts': {
                'S3ModelArtifacts': 's3://bucket/model.tar.gz'
            }
        })
        return mock_client
    
    def test_init_with_valid_parameters(self, mock_sagemaker_client, valid_pipeline_config):
        """Test initialization with valid sagemaker_client and config"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        assert trainer.sagemaker_client is mock_sagemaker_client
        assert trainer.config is valid_pipeline_config
    
    def test_init_stores_sagemaker_client(self, mock_sagemaker_client, valid_pipeline_config):
        """Test that sagemaker_client is properly stored"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        assert hasattr(trainer, 'sagemaker_client')
        assert trainer.sagemaker_client is mock_sagemaker_client
    
    def test_init_stores_config(self, mock_sagemaker_client, valid_pipeline_config):
        """Test that config is properly stored"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        assert hasattr(trainer, 'config')
        assert trainer.config is valid_pipeline_config
    
    def test_init_with_none_sagemaker_client(self, valid_pipeline_config):
        """Test that None sagemaker_client raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            ModelTrainer(None, valid_pipeline_config)
        
        assert "sagemaker_client cannot be None" in str(exc_info.value)
    
    def test_init_with_none_config(self, mock_sagemaker_client):
        """Test that None config raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            ModelTrainer(mock_sagemaker_client, None)
        
        assert "config cannot be None" in str(exc_info.value)
    
    def test_init_with_both_none(self):
        """Test that both None parameters raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            ModelTrainer(None, None)
        
        # Should fail on sagemaker_client first
        assert "sagemaker_client cannot be None" in str(exc_info.value)
    
    def test_init_with_invalid_config_type(self, mock_sagemaker_client):
        """Test that non-PipelineConfig config raises TypeError"""
        invalid_config = {
            'aws_region': 'us-east-1',
            'sagemaker_role_arn': 'arn:aws:iam::123456789012:role/SageMakerRole'
        }
        
        with pytest.raises(TypeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, invalid_config)
        
        assert "config must be a PipelineConfig instance" in str(exc_info.value)
        assert "dict" in str(exc_info.value)
    
    def test_init_with_string_config(self, mock_sagemaker_client):
        """Test that string config raises TypeError"""
        with pytest.raises(TypeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, "not a config")
        
        assert "config must be a PipelineConfig instance" in str(exc_info.value)
        assert "str" in str(exc_info.value)
    
    def test_init_with_incomplete_config(self, mock_sagemaker_client):
        """Test that config missing required attributes raises AttributeError"""
        # Create a mock object that passes isinstance check but lacks attributes
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        
        # Remove required attributes
        del incomplete_config.sagemaker_role_arn
        del incomplete_config.training_instance_type
        del incomplete_config.aws_region
        
        with pytest.raises(AttributeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "sagemaker_role_arn" in error_msg
        assert "training_instance_type" in error_msg
        assert "aws_region" in error_msg
    
    def test_init_with_config_missing_sagemaker_role_arn(self, mock_sagemaker_client):
        """Test that config without sagemaker_role_arn raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.training_instance_type = "ml.g5.2xlarge"
        incomplete_config.s3_bucket = "my-bucket"
        incomplete_config.base_model = "meta-llama/Llama-3.2-3B"
        incomplete_config.max_training_time_seconds = 86400
        incomplete_config.max_retries = 3
        incomplete_config.initial_backoff_seconds = 2
        incomplete_config.max_backoff_seconds = 60
        
        # Remove sagemaker_role_arn
        del incomplete_config.sagemaker_role_arn
        
        with pytest.raises(AttributeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "sagemaker_role_arn" in error_msg
    
    def test_init_with_config_missing_training_instance_type(self, mock_sagemaker_client):
        """Test that config without training_instance_type raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        incomplete_config.s3_bucket = "my-bucket"
        incomplete_config.base_model = "meta-llama/Llama-3.2-3B"
        incomplete_config.max_training_time_seconds = 86400
        incomplete_config.max_retries = 3
        incomplete_config.initial_backoff_seconds = 2
        incomplete_config.max_backoff_seconds = 60
        
        # Remove training_instance_type
        del incomplete_config.training_instance_type
        
        with pytest.raises(AttributeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "training_instance_type" in error_msg
    
    def test_init_with_config_missing_s3_bucket(self, mock_sagemaker_client):
        """Test that config without s3_bucket raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        incomplete_config.training_instance_type = "ml.g5.2xlarge"
        incomplete_config.base_model = "meta-llama/Llama-3.2-3B"
        incomplete_config.max_training_time_seconds = 86400
        incomplete_config.max_retries = 3
        incomplete_config.initial_backoff_seconds = 2
        incomplete_config.max_backoff_seconds = 60
        
        # Remove s3_bucket
        del incomplete_config.s3_bucket
        
        with pytest.raises(AttributeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "s3_bucket" in error_msg
    
    def test_init_with_config_missing_base_model(self, mock_sagemaker_client):
        """Test that config without base_model raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        incomplete_config.training_instance_type = "ml.g5.2xlarge"
        incomplete_config.s3_bucket = "my-bucket"
        incomplete_config.max_training_time_seconds = 86400
        incomplete_config.max_retries = 3
        incomplete_config.initial_backoff_seconds = 2
        incomplete_config.max_backoff_seconds = 60
        
        # Remove base_model
        del incomplete_config.base_model
        
        with pytest.raises(AttributeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "base_model" in error_msg
    
    def test_init_with_config_missing_retry_settings(self, mock_sagemaker_client):
        """Test that config without retry settings raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.sagemaker_role_arn = "arn:aws:iam::123456789012:role/SageMakerRole"
        incomplete_config.training_instance_type = "ml.g5.2xlarge"
        incomplete_config.s3_bucket = "my-bucket"
        incomplete_config.base_model = "meta-llama/Llama-3.2-3B"
        incomplete_config.max_training_time_seconds = 86400
        
        # Remove retry settings
        del incomplete_config.max_retries
        del incomplete_config.initial_backoff_seconds
        del incomplete_config.max_backoff_seconds
        
        with pytest.raises(AttributeError) as exc_info:
            ModelTrainer(mock_sagemaker_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        # Should mention at least one of the missing retry attributes
        assert any(attr in error_msg for attr in [
            "max_retries", "initial_backoff_seconds", "max_backoff_seconds"
        ])
    
    def test_init_logs_initialization(self, mock_sagemaker_client, valid_pipeline_config, caplog):
        """Test that initialization is logged"""
        import logging
        caplog.set_level(logging.INFO)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Check that initialization was logged
        assert any("ModelTrainer initialized" in record.message for record in caplog.records)
    
    def test_init_with_different_instance_types(self, mock_sagemaker_client):
        """Test initialization with various instance types"""
        instance_types = [
            "ml.g5.xlarge",
            "ml.g5.2xlarge",
            "ml.g5.4xlarge",
            "ml.p3.2xlarge",
            "ml.p4d.24xlarge"
        ]
        
        for instance_type in instance_types:
            config = PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type=instance_type,
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-finetuning-bucket"
            )
            
            trainer = ModelTrainer(mock_sagemaker_client, config)
            assert trainer.config.training_instance_type == instance_type
    
    def test_init_with_different_regions(self, mock_sagemaker_client):
        """Test initialization with various AWS regions"""
        regions = [
            "us-east-1",
            "us-west-2",
            "eu-west-1",
            "ap-southeast-1"
        ]
        
        for region in regions:
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
                s3_bucket="my-finetuning-bucket"
            )
            
            trainer = ModelTrainer(mock_sagemaker_client, config)
            assert trainer.config.aws_region == region
    
    def test_init_preserves_all_config_attributes(self, mock_sagemaker_client, valid_pipeline_config):
        """Test that all config attributes are accessible after initialization"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Verify all required attributes are accessible
        assert trainer.config.sagemaker_role_arn == valid_pipeline_config.sagemaker_role_arn
        assert trainer.config.training_instance_type == valid_pipeline_config.training_instance_type
        assert trainer.config.aws_region == valid_pipeline_config.aws_region
        assert trainer.config.s3_bucket == valid_pipeline_config.s3_bucket
        assert trainer.config.base_model == valid_pipeline_config.base_model
        assert trainer.config.max_training_time_seconds == valid_pipeline_config.max_training_time_seconds
        assert trainer.config.max_retries == valid_pipeline_config.max_retries
        assert trainer.config.initial_backoff_seconds == valid_pipeline_config.initial_backoff_seconds
        assert trainer.config.max_backoff_seconds == valid_pipeline_config.max_backoff_seconds



class TestModelTrainerTrainModel:
    """Test suite for ModelTrainer.train_model() method"""
    
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
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client with training job responses"""
        from datetime import datetime, timedelta
        
        mock_client = Mock()
        
        # Mock create_training_job
        mock_client.create_training_job = Mock(return_value={
            'TrainingJobArn': 'arn:aws:sagemaker:us-east-1:123456789012:training-job/test-job'
        })
        
        # Mock describe_training_job - return completed status
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        
        mock_client.describe_training_job = Mock(return_value={
            'TrainingJobStatus': 'Completed',
            'TrainingStartTime': start_time,
            'TrainingEndTime': end_time,
            'ModelArtifacts': {
                'S3ModelArtifacts': 's3://bucket/model-artifacts/model.tar.gz'
            },
            'FinalMetricDataList': [
                {'MetricName': 'train:loss', 'Value': 0.25}
            ]
        })
        
        return mock_client
    
    @pytest.fixture
    def training_data_file(self, tmp_path):
        """Create a temporary training data file"""
        data_file = tmp_path / "training_data.jsonl"
        data_file.write_text(
            '{"instruction": "Test", "context": "Context", "response": "Response"}\n'
        )
        return str(data_file)
    
    @pytest.fixture
    def mock_s3_upload(self, monkeypatch):
        """Mock S3 upload functionality"""
        mock_upload = Mock(return_value=None)
        
        def mock_upload_file(*args, **kwargs):
            return None
        
        # Mock boto3.client to return a mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.upload_file = mock_upload_file
        
        def mock_boto3_client(service, **kwargs):
            if service == 's3':
                return mock_s3_client
            return Mock()
        
        import boto3
        monkeypatch.setattr(boto3, 'client', mock_boto3_client)
        
        return mock_upload
    
    def test_train_model_with_valid_inputs(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload
    ):
        """Test train_model with valid inputs returns successful result"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        result = trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        assert isinstance(result, TrainingResult)
        assert result.status == "Completed"
        assert result.is_successful()
    
    def test_train_model_calls_create_training_job(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload
    ):
        """Test that train_model calls SageMaker create_training_job"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        assert mock_sagemaker_client.create_training_job.called
    
    def test_train_model_with_nonexistent_file(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that train_model raises FileNotFoundError for nonexistent file"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            trainer.train_model(
                training_data_path="/nonexistent/file.jsonl",
                use_case_name="test_use_case"
            )
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_train_model_with_empty_file(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        tmp_path
    ):
        """Test that train_model raises ValueError for empty file"""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.write_text("")
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            trainer.train_model(
                training_data_path=str(empty_file),
                use_case_name="test_use_case"
            )
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_train_model_with_custom_hyperparameters(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload
    ):
        """Test train_model with custom hyperparameters"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        custom_hyperparameters = {
            "epochs": "5",
            "learning_rate": "0.0002",
            "per_device_train_batch_size": "16"
        }
        
        result = trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case",
            hyperparameters=custom_hyperparameters
        )
        
        assert result.is_successful()
        # Verify custom hyperparameters were used
        call_args = mock_sagemaker_client.create_training_job.call_args
        assert call_args is not None
    
    def test_train_model_returns_training_result(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload
    ):
        """Test that train_model returns a TrainingResult object"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        result = trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        assert isinstance(result, TrainingResult)
        assert hasattr(result, 'job_name')
        assert hasattr(result, 'model_artifact_s3_uri')
        assert hasattr(result, 'training_time_seconds')
        assert hasattr(result, 'final_loss')
        assert hasattr(result, 'status')
    
    def test_train_model_with_failed_training_job(
        self,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload
    ):
        """Test train_model handles failed training job"""
        from datetime import datetime, timedelta
        
        mock_client = Mock()
        mock_client.create_training_job = Mock(return_value={
            'TrainingJobArn': 'arn:aws:sagemaker:us-east-1:123456789012:training-job/test-job'
        })
        
        # Mock failed training job
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=30)
        
        mock_client.describe_training_job = Mock(return_value={
            'TrainingJobStatus': 'Failed',
            'TrainingStartTime': start_time,
            'TrainingEndTime': end_time,
            'ModelArtifacts': {
                'S3ModelArtifacts': ''
            },
            'FailureReason': 'Out of memory error',
            'FinalMetricDataList': []
        })
        
        trainer = ModelTrainer(mock_client, valid_pipeline_config)
        
        result = trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        assert result.status == "Failed"
        assert not result.is_successful()
        assert result.error_message is not None
        assert "memory" in result.error_message.lower()
    
    def test_train_model_generates_unique_job_names(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload
    ):
        """Test that train_model generates unique job names with timestamps"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Train twice
        trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        first_call_args = mock_sagemaker_client.create_training_job.call_args
        first_job_name = first_call_args[1]['TrainingJobName']
        
        # Longer delay to ensure different timestamp (1 second resolution)
        import time
        time.sleep(1.1)
        
        trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        second_call_args = mock_sagemaker_client.create_training_job.call_args
        second_job_name = second_call_args[1]['TrainingJobName']
        
        # Job names should be different due to timestamps
        assert first_job_name != second_job_name
        assert "test_use_case" in first_job_name
        assert "test_use_case" in second_job_name
    
    def test_train_model_uploads_data_to_s3(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        monkeypatch
    ):
        """Test that train_model uploads training data to S3"""
        upload_called = []
        
        def mock_upload_file(Filename, Bucket, Key):
            upload_called.append({
                'filename': Filename,
                'bucket': Bucket,
                'key': Key
            })
        
        mock_s3_client = Mock()
        mock_s3_client.upload_file = mock_upload_file
        
        def mock_boto3_client(service, **kwargs):
            if service == 's3':
                return mock_s3_client
            return Mock()
        
        import boto3
        monkeypatch.setattr(boto3, 'client', mock_boto3_client)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        assert len(upload_called) == 1
        assert upload_called[0]['bucket'] == valid_pipeline_config.s3_bucket
        assert 'test_use_case' in upload_called[0]['key']
    
    def test_train_model_uses_default_hyperparameters_when_none_provided(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload
    ):
        """Test that train_model uses default hyperparameters when none provided"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        result = trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case",
            hyperparameters=None
        )
        
        assert result.is_successful()
        
        # Verify create_training_job was called with hyperparameters
        call_args = mock_sagemaker_client.create_training_job.call_args
        assert 'HyperParameters' in call_args[1]
        hyperparams = call_args[1]['HyperParameters']
        
        # Check for expected default hyperparameters
        assert 'epochs' in hyperparams
        assert 'learning_rate' in hyperparams
    
    def test_train_model_logs_progress(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        training_data_file,
        mock_s3_upload,
        caplog
    ):
        """Test that train_model logs progress messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        trainer.train_model(
            training_data_path=training_data_file,
            use_case_name="test_use_case"
        )
        
        # Check for key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Starting model training" in msg for msg in log_messages)
        assert any("Training completed successfully" in msg or "Training job finished" in msg for msg in log_messages)


class TestModelTrainerDetermineHyperparameters:
    """Test suite for ModelTrainer._determine_hyperparameters() method"""
    
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
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        return Mock()
    
    def test_determine_hyperparameters_returns_dict(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _determine_hyperparameters returns a dictionary"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        analysis = DatasetAnalysis(
            num_examples=1000,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=32
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        assert isinstance(hyperparams, dict)
        assert len(hyperparams) > 0
    
    def test_determine_hyperparameters_includes_all_required_params(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that hyperparameters include all required training parameters"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        analysis = DatasetAnalysis(
            num_examples=500,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=5,
            recommended_batch_size=16
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Check for all required hyperparameters
        assert 'epochs' in hyperparams
        assert 'learning_rate' in hyperparams
        assert 'per_device_train_batch_size' in hyperparams
        assert 'lora_r' in hyperparams
        assert 'lora_alpha' in hyperparams
        assert 'lora_dropout' in hyperparams
    
    def test_determine_hyperparameters_uses_recommended_epochs(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that epochs are taken from dataset analysis recommendations"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        analysis = DatasetAnalysis(
            num_examples=1000,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=32
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        assert hyperparams['epochs'] == '3'
    
    def test_determine_hyperparameters_uses_recommended_batch_size(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that batch size is taken from dataset analysis recommendations"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        analysis = DatasetAnalysis(
            num_examples=500,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=5,
            recommended_batch_size=16
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        assert hyperparams['per_device_train_batch_size'] == '16'
    
    def test_determine_hyperparameters_large_dataset_small_learning_rate(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that large datasets get smaller learning rate"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Large dataset (>= 1000 examples)
        analysis = DatasetAnalysis(
            num_examples=1500,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=32
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Large dataset should get learning rate of 0.0001
        assert hyperparams['learning_rate'] == '0.0001'
    
    def test_determine_hyperparameters_medium_dataset_medium_learning_rate(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that medium datasets get medium learning rate"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Medium dataset (500-999 examples)
        analysis = DatasetAnalysis(
            num_examples=750,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=5,
            recommended_batch_size=16
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Medium dataset should get learning rate of 0.00015
        assert hyperparams['learning_rate'] == '0.00015'
    
    def test_determine_hyperparameters_small_medium_dataset_larger_learning_rate(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that small-medium datasets get larger learning rate"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Small-medium dataset (200-499 examples)
        analysis = DatasetAnalysis(
            num_examples=300,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=7,
            recommended_batch_size=8
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Small-medium dataset should get learning rate of 0.0002
        assert hyperparams['learning_rate'] == '0.0002'
    
    def test_determine_hyperparameters_small_dataset_largest_learning_rate(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that small datasets get largest learning rate"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Small dataset (< 200 examples)
        analysis = DatasetAnalysis(
            num_examples=100,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=10,
            recommended_batch_size=4
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Small dataset should get learning rate of 0.0003
        assert hyperparams['learning_rate'] == '0.0003'
    
    def test_determine_hyperparameters_large_dataset_high_lora_rank(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that large datasets get higher LoRA rank"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Large dataset (>= 1000 examples)
        analysis = DatasetAnalysis(
            num_examples=1500,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=32
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Large dataset should get lora_r of 16
        assert hyperparams['lora_r'] == '16'
        # lora_alpha should be 2x lora_r
        assert hyperparams['lora_alpha'] == '32'
    
    def test_determine_hyperparameters_medium_dataset_medium_lora_rank(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that medium datasets get medium LoRA rank"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Medium dataset (500-999 examples)
        analysis = DatasetAnalysis(
            num_examples=750,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=5,
            recommended_batch_size=16
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Medium dataset should get lora_r of 12
        assert hyperparams['lora_r'] == '12'
        # lora_alpha should be 2x lora_r
        assert hyperparams['lora_alpha'] == '24'
    
    def test_determine_hyperparameters_small_dataset_low_lora_rank(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that small datasets get lower LoRA rank"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Small dataset (< 500 examples)
        analysis = DatasetAnalysis(
            num_examples=300,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=7,
            recommended_batch_size=8
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Small dataset should get lora_r of 8
        assert hyperparams['lora_r'] == '8'
        # lora_alpha should be 2x lora_r
        assert hyperparams['lora_alpha'] == '16'
    
    def test_determine_hyperparameters_lora_alpha_is_double_lora_r(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that lora_alpha is always 2x lora_r"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Test with various dataset sizes
        dataset_sizes = [100, 300, 750, 1500]
        
        for size in dataset_sizes:
            analysis = DatasetAnalysis(
                num_examples=size,
                avg_instruction_length=100,
                avg_response_length=200,
                recommended_epochs=5,
                recommended_batch_size=16
            )
            
            hyperparams = trainer._determine_hyperparameters(analysis)
            
            lora_r = int(hyperparams['lora_r'])
            lora_alpha = int(hyperparams['lora_alpha'])
            
            assert lora_alpha == lora_r * 2
    
    def test_determine_hyperparameters_lora_dropout_is_fixed(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that lora_dropout is always 0.1"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Test with various dataset sizes
        dataset_sizes = [100, 300, 750, 1500]
        
        for size in dataset_sizes:
            analysis = DatasetAnalysis(
                num_examples=size,
                avg_instruction_length=100,
                avg_response_length=200,
                recommended_epochs=5,
                recommended_batch_size=16
            )
            
            hyperparams = trainer._determine_hyperparameters(analysis)
            
            # lora_dropout should always be 0.1
            assert hyperparams['lora_dropout'] == '0.1'
    
    def test_determine_hyperparameters_all_values_are_strings(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that all hyperparameter values are strings (SageMaker requirement)"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        analysis = DatasetAnalysis(
            num_examples=1000,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=32
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # All values should be strings
        for key, value in hyperparams.items():
            assert isinstance(value, str), f"{key} value should be string, got {type(value)}"
    
    def test_determine_hyperparameters_boundary_1000_examples(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test hyperparameters at boundary of 1000 examples"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Exactly 1000 examples (should be treated as large dataset)
        analysis = DatasetAnalysis(
            num_examples=1000,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=32
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Should get large dataset parameters
        assert hyperparams['learning_rate'] == '0.0001'
        assert hyperparams['lora_r'] == '16'
    
    def test_determine_hyperparameters_boundary_500_examples(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test hyperparameters at boundary of 500 examples"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Exactly 500 examples (should be treated as medium dataset)
        analysis = DatasetAnalysis(
            num_examples=500,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=5,
            recommended_batch_size=16
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Should get medium dataset parameters
        assert hyperparams['learning_rate'] == '0.00015'
        assert hyperparams['lora_r'] == '12'
    
    def test_determine_hyperparameters_boundary_200_examples(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test hyperparameters at boundary of 200 examples"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Exactly 200 examples (should be treated as small-medium dataset)
        analysis = DatasetAnalysis(
            num_examples=200,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=7,
            recommended_batch_size=8
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Should get small-medium dataset parameters
        assert hyperparams['learning_rate'] == '0.0002'
        assert hyperparams['lora_r'] == '8'
    
    def test_determine_hyperparameters_very_large_dataset(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test hyperparameters with very large dataset"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Very large dataset
        analysis = DatasetAnalysis(
            num_examples=10000,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=2,
            recommended_batch_size=64
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Should still get large dataset parameters
        assert hyperparams['learning_rate'] == '0.0001'
        assert hyperparams['lora_r'] == '16'
        assert hyperparams['lora_alpha'] == '32'
    
    def test_determine_hyperparameters_very_small_dataset(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test hyperparameters with very small dataset"""
        from src.config_models import DatasetAnalysis
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Very small dataset
        analysis = DatasetAnalysis(
            num_examples=50,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=15,
            recommended_batch_size=2
        )
        
        hyperparams = trainer._determine_hyperparameters(analysis)
        
        # Should get small dataset parameters
        assert hyperparams['learning_rate'] == '0.0003'
        assert hyperparams['lora_r'] == '8'
        assert hyperparams['lora_alpha'] == '16'
    
    def test_determine_hyperparameters_logs_progress(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        caplog
    ):
        """Test that _determine_hyperparameters logs progress"""
        import logging
        from src.config_models import DatasetAnalysis
        
        caplog.set_level(logging.INFO)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        analysis = DatasetAnalysis(
            num_examples=1000,
            avg_instruction_length=100,
            avg_response_length=200,
            recommended_epochs=3,
            recommended_batch_size=32
        )
        
        trainer._determine_hyperparameters(analysis)
        
        # Check for log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Determining hyperparameters" in msg for msg in log_messages)
        assert any("Hyperparameters determined" in msg for msg in log_messages)


class TestModelTrainerPrivateMethods:
    """Test suite for ModelTrainer private helper methods"""
    
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
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        return Mock()
    
    def test_get_default_hyperparameters_returns_dict(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _get_default_hyperparameters returns a dictionary"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        hyperparams = trainer._get_default_hyperparameters()
        
        assert isinstance(hyperparams, dict)
        assert len(hyperparams) > 0
    
    def test_get_default_hyperparameters_includes_required_params(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that default hyperparameters include required training parameters"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        hyperparams = trainer._get_default_hyperparameters()
        
        # Check for essential hyperparameters
        assert 'epochs' in hyperparams
        assert 'learning_rate' in hyperparams
        assert 'per_device_train_batch_size' in hyperparams
    
    def test_get_training_image_returns_string(
        self,
        mock_sagemaker_client,
        valid_pipeline_config
    ):
        """Test that _get_training_image returns a string"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        image_uri = trainer._get_training_image()
        
        assert isinstance(image_uri, str)
        assert len(image_uri) > 0
    
    def test_wait_for_training_polls_until_completion(
        self,
        valid_pipeline_config
    ):
        """Test that _wait_for_training polls until job completes"""
        from datetime import datetime, timedelta
        
        mock_client = Mock()
        
        # Simulate job progressing through states
        call_count = [0]
        
        def mock_describe(TrainingJobName):
            call_count[0] += 1
            start_time = datetime.now()
            
            if call_count[0] < 3:
                return {
                    'TrainingJobStatus': 'InProgress',
                    'TrainingStartTime': start_time,
                    'TrainingEndTime': start_time + timedelta(seconds=100),
                    'ModelArtifacts': {'S3ModelArtifacts': 's3://bucket/model.tar.gz'},
                    'FinalMetricDataList': []
                }
            else:
                return {
                    'TrainingJobStatus': 'Completed',
                    'TrainingStartTime': start_time,
                    'TrainingEndTime': start_time + timedelta(hours=1),
                    'ModelArtifacts': {'S3ModelArtifacts': 's3://bucket/model.tar.gz'},
                    'FinalMetricDataList': [{'MetricName': 'train:loss', 'Value': 0.25}]
                }
        
        mock_client.describe_training_job = mock_describe
        
        trainer = ModelTrainer(mock_client, valid_pipeline_config)
        
        result = trainer._wait_for_training("test-job", poll_interval=0.1)
        
        assert result.status == "Completed"
        assert call_count[0] >= 3  # Should have polled multiple times



class TestModelTrainerCleanupTrainingArtifacts:
    """Test suite for ModelTrainer.cleanup_training_artifacts() method"""
    
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
            s3_bucket="my-finetuning-bucket",
            base_model="meta-llama/Llama-3.2-3B",
            max_training_time_seconds=86400,
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60,
            artifact_retention_days=7
        )
    
    @pytest.fixture
    def mock_sagemaker_client(self):
        """Create a mock SageMaker client"""
        from datetime import datetime, timedelta
        
        mock_client = Mock()
        
        # Mock describe_training_job - return old job (> 7 days)
        creation_time = datetime.now() - timedelta(days=10)
        
        mock_client.describe_training_job = Mock(return_value={
            'TrainingJobName': 'test-job',
            'CreationTime': creation_time,
            'TrainingJobStatus': 'Completed',
            'InputDataConfig': [
                {
                    'ChannelName': 'training',
                    'DataSource': {
                        'S3DataSource': {
                            'S3Uri': 's3://my-bucket/training-data/test-job/data.jsonl'
                        }
                    }
                }
            ],
            'ModelArtifacts': {
                'S3ModelArtifacts': 's3://my-bucket/model-artifacts/test-job/model.tar.gz'
            }
        })
        
        # Add exception types
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        
        return mock_client
    
    @pytest.fixture
    def mock_s3_client(self, monkeypatch):
        """Mock boto3 S3 client"""
        mock_s3 = Mock()
        
        # Mock list_objects_v2 paginator
        mock_paginator = Mock()
        mock_pages = [
            {
                'Contents': [
                    {'Key': 'training-data/test-job/data.jsonl'},
                ]
            }
        ]
        mock_paginator.paginate = Mock(return_value=mock_pages)
        mock_s3.get_paginator = Mock(return_value=mock_paginator)
        
        # Mock delete_objects
        mock_s3.delete_objects = Mock(return_value={
            'Deleted': [{'Key': 'training-data/test-job/data.jsonl'}],
            'Errors': []
        })
        
        # Add exception types
        mock_s3.exceptions = Mock()
        mock_s3.exceptions.NoSuchBucket = type('NoSuchBucket', (Exception,), {})
        mock_s3.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        
        # Mock boto3.client to return our mock S3 client
        def mock_boto3_client(service, **kwargs):
            if service == 's3':
                return mock_s3
            return Mock()
        
        import boto3
        monkeypatch.setattr(boto3, 'client', mock_boto3_client)
        
        return mock_s3
    
    def test_cleanup_with_valid_job_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test cleanup with valid job name succeeds"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Should not raise any exception
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # Verify SageMaker describe was called
        assert mock_sagemaker_client.describe_training_job.called
    
    def test_cleanup_with_none_job_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that None job_name raises ValueError"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            trainer.cleanup_training_artifacts(
                job_name=None,
                retention_days=7
            )
        
        assert "job_name cannot be None or empty" in str(exc_info.value)
    
    def test_cleanup_with_empty_job_name(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that empty job_name raises ValueError"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            trainer.cleanup_training_artifacts(
                job_name="",
                retention_days=7
            )
        
        assert "job_name cannot be None or empty" in str(exc_info.value)
    
    def test_cleanup_with_negative_retention_days(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that negative retention_days raises ValueError"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            trainer.cleanup_training_artifacts(
                job_name="test-job",
                retention_days=-1
            )
        
        assert "retention_days must be non-negative" in str(exc_info.value)
    
    def test_cleanup_skips_recent_artifacts(
        self,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that cleanup skips artifacts newer than retention period"""
        from datetime import datetime, timedelta
        
        # Create mock with recent job (only 3 days old)
        mock_client = Mock()
        creation_time = datetime.now() - timedelta(days=3)
        
        mock_client.describe_training_job = Mock(return_value={
            'TrainingJobName': 'test-job',
            'CreationTime': creation_time,
            'TrainingJobStatus': 'Completed',
            'InputDataConfig': [],
            'ModelArtifacts': {}
        })
        
        trainer = ModelTrainer(mock_client, valid_pipeline_config)
        
        # Should not delete anything (job is only 3 days old, retention is 7)
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # S3 delete should not be called
        assert not mock_s3_client.delete_objects.called
    
    def test_cleanup_deletes_old_artifacts(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that cleanup deletes artifacts older than retention period"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Job is 10 days old, retention is 7 days
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # S3 delete should be called
        assert mock_s3_client.delete_objects.called
    
    def test_cleanup_with_zero_retention_days(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that retention_days=0 deletes immediately"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Should delete regardless of age
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=0
        )
        
        # S3 delete should be called
        assert mock_s3_client.delete_objects.called
    
    def test_cleanup_handles_nonexistent_job(
        self,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that cleanup handles nonexistent training job gracefully"""
        mock_client = Mock()
        
        # Mock ResourceNotFound exception
        ResourceNotFound = type('ResourceNotFound', (Exception,), {})
        mock_client.exceptions = Mock()
        mock_client.exceptions.ResourceNotFound = ResourceNotFound
        
        mock_client.describe_training_job = Mock(
            side_effect=ResourceNotFound("Job not found")
        )
        
        trainer = ModelTrainer(mock_client, valid_pipeline_config)
        
        # Should not raise exception
        trainer.cleanup_training_artifacts(
            job_name="nonexistent-job",
            retention_days=7
        )
    
    def test_cleanup_deletes_training_data(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that cleanup deletes training data from S3"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # Verify S3 operations were called
        assert mock_s3_client.get_paginator.called
        assert mock_s3_client.delete_objects.called
    
    def test_cleanup_deletes_model_artifacts(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that cleanup deletes model artifacts from S3"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # Verify S3 delete was called (for both training data and model artifacts)
        assert mock_s3_client.delete_objects.call_count >= 1
    
    def test_cleanup_handles_missing_s3_objects(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        monkeypatch
    ):
        """Test that cleanup handles missing S3 objects gracefully"""
        # Mock S3 client that returns no objects
        mock_s3 = Mock()
        
        mock_paginator = Mock()
        mock_pages = [{}]  # No 'Contents' key - no objects found
        mock_paginator.paginate = Mock(return_value=mock_pages)
        mock_s3.get_paginator = Mock(return_value=mock_paginator)
        
        mock_s3.delete_objects = Mock()
        mock_s3.exceptions = Mock()
        mock_s3.exceptions.NoSuchBucket = type('NoSuchBucket', (Exception,), {})
        mock_s3.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        
        def mock_boto3_client(service, **kwargs):
            if service == 's3':
                return mock_s3
            return Mock()
        
        import boto3
        monkeypatch.setattr(boto3, 'client', mock_boto3_client)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Should not raise exception even if objects don't exist
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # Delete should not be called if no objects found
        assert not mock_s3.delete_objects.called
    
    def test_cleanup_logs_operations(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client,
        caplog
    ):
        """Test that cleanup logs all operations"""
        import logging
        caplog.set_level(logging.INFO)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # Check for key log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Starting cleanup" in msg for msg in log_messages)
        assert any("Cleanup completed" in msg or "Deleted" in msg for msg in log_messages)
    
    def test_cleanup_is_idempotent(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that cleanup can be called multiple times safely"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Call cleanup twice
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # Should not raise any exception
        assert True
    
    def test_cleanup_handles_s3_errors_gracefully(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        monkeypatch
    ):
        """Test that cleanup handles S3 errors without failing"""
        # Mock S3 client that raises errors
        mock_s3 = Mock()
        
        mock_paginator = Mock()
        mock_paginator.paginate = Mock(side_effect=Exception("S3 error"))
        mock_s3.get_paginator = Mock(return_value=mock_paginator)
        
        mock_s3.exceptions = Mock()
        mock_s3.exceptions.NoSuchBucket = type('NoSuchBucket', (Exception,), {})
        mock_s3.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        
        def mock_boto3_client(service, **kwargs):
            if service == 's3':
                return mock_s3
            return Mock()
        
        import boto3
        monkeypatch.setattr(boto3, 'client', mock_boto3_client)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Should log error but not raise exception
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
    
    def test_cleanup_with_default_retention_days(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test that cleanup uses default retention_days of 7"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Call without specifying retention_days
        trainer.cleanup_training_artifacts(job_name="test-job")
        
        # Should use default of 7 days
        assert mock_sagemaker_client.describe_training_job.called
    
    def test_cleanup_handles_access_denied_error(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        monkeypatch,
        caplog
    ):
        """Test that cleanup logs warning for access denied errors but continues"""
        import logging
        caplog.set_level(logging.WARNING)
        
        # Mock S3 client that raises AccessDenied
        mock_s3 = Mock()
        
        mock_paginator = Mock()
        mock_paginator.paginate = Mock(side_effect=Exception("AccessDenied"))
        mock_s3.get_paginator = Mock(return_value=mock_paginator)
        
        mock_s3.exceptions = Mock()
        mock_s3.exceptions.NoSuchBucket = type('NoSuchBucket', (Exception,), {})
        mock_s3.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        
        def mock_boto3_client(service, **kwargs):
            if service == 's3':
                return mock_s3
            return Mock()
        
        import boto3
        monkeypatch.setattr(boto3, 'client', mock_boto3_client)
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        # Should log warning but not raise exception (best-effort cleanup)
        trainer.cleanup_training_artifacts(
            job_name="test-job",
            retention_days=7
        )
        
        # Verify warning was logged
        log_messages = [record.message for record in caplog.records]
        assert any("Failed to delete" in msg and "AccessDenied" in msg for msg in log_messages)
    
    def test_delete_s3_objects_with_valid_uri(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test _delete_s3_objects with valid S3 URI"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        count = trainer._delete_s3_objects(
            mock_s3_client,
            "s3://my-bucket/path/to/object.tar.gz"
        )
        
        assert isinstance(count, int)
        assert count >= 0
    
    def test_delete_s3_objects_with_invalid_uri(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        mock_s3_client
    ):
        """Test _delete_s3_objects with invalid URI raises ValueError"""
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            trainer._delete_s3_objects(
                mock_s3_client,
                "not-an-s3-uri"
            )
        
        assert "Invalid S3 URI" in str(exc_info.value)
    
    def test_delete_s3_objects_handles_batch_deletion(
        self,
        mock_sagemaker_client,
        valid_pipeline_config,
        monkeypatch
    ):
        """Test _delete_s3_objects handles large batches correctly"""
        # Mock S3 client with many objects
        mock_s3 = Mock()
        
        # Create 1500 objects (more than batch size of 1000)
        objects = [{'Key': f'object-{i}'} for i in range(1500)]
        
        mock_paginator = Mock()
        mock_pages = [{'Contents': objects}]
        mock_paginator.paginate = Mock(return_value=mock_pages)
        mock_s3.get_paginator = Mock(return_value=mock_paginator)
        
        # Track delete calls
        delete_calls = []
        
        def mock_delete(Bucket, Delete):
            delete_calls.append(len(Delete['Objects']))
            return {
                'Deleted': Delete['Objects'],
                'Errors': []
            }
        
        mock_s3.delete_objects = mock_delete
        mock_s3.exceptions = Mock()
        mock_s3.exceptions.NoSuchBucket = type('NoSuchBucket', (Exception,), {})
        mock_s3.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        
        trainer = ModelTrainer(mock_sagemaker_client, valid_pipeline_config)
        
        count = trainer._delete_s3_objects(
            mock_s3,
            "s3://my-bucket/path/"
        )
        
        # Should have made 2 delete calls (1000 + 500)
        assert len(delete_calls) == 2
        assert delete_calls[0] == 1000
        assert delete_calls[1] == 500
        assert count == 1500
