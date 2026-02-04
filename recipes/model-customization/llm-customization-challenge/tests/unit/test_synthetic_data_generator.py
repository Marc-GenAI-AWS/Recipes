"""
Unit tests for SyntheticDataGenerator class.

Tests cover:
- __init__ method with valid and invalid parameters
- Bedrock client initialization
- Configuration validation
- Error handling for missing or invalid inputs
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.synthetic_data_generator import SyntheticDataGenerator
from src.config_models import PipelineConfig


class TestSyntheticDataGeneratorInit:
    """Test suite for SyntheticDataGenerator.__init__ method"""
    
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
    def mock_bedrock_client(self):
        """Create a mock Bedrock Runtime client"""
        mock_client = Mock()
        mock_client.invoke_model = Mock(return_value={
            'body': Mock(),
            'contentType': 'application/json'
        })
        return mock_client
    
    def test_init_with_valid_parameters(self, mock_bedrock_client, valid_pipeline_config):
        """Test initialization with valid bedrock_client and config"""
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        assert generator.bedrock_client is mock_bedrock_client
        assert generator.config is valid_pipeline_config
        assert generator.model_id == valid_pipeline_config.bedrock_model_id
    
    def test_init_stores_bedrock_client(self, mock_bedrock_client, valid_pipeline_config):
        """Test that bedrock_client is properly stored"""
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        assert hasattr(generator, 'bedrock_client')
        assert generator.bedrock_client is mock_bedrock_client
    
    def test_init_stores_config(self, mock_bedrock_client, valid_pipeline_config):
        """Test that config is properly stored"""
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        assert hasattr(generator, 'config')
        assert generator.config is valid_pipeline_config
    
    def test_init_extracts_model_id(self, mock_bedrock_client, valid_pipeline_config):
        """Test that model_id is extracted from config"""
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        assert hasattr(generator, 'model_id')
        assert generator.model_id == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert generator.model_id == valid_pipeline_config.bedrock_model_id
    
    def test_init_with_none_bedrock_client(self, valid_pipeline_config):
        """Test that None bedrock_client raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            SyntheticDataGenerator(None, valid_pipeline_config)
        
        assert "bedrock_client cannot be None" in str(exc_info.value)
    
    def test_init_with_none_config(self, mock_bedrock_client):
        """Test that None config raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            SyntheticDataGenerator(mock_bedrock_client, None)
        
        assert "config cannot be None" in str(exc_info.value)
    
    def test_init_with_both_none(self):
        """Test that both None parameters raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            SyntheticDataGenerator(None, None)
        
        # Should fail on bedrock_client first
        assert "bedrock_client cannot be None" in str(exc_info.value)
    
    def test_init_with_invalid_config_type(self, mock_bedrock_client):
        """Test that non-PipelineConfig config raises TypeError"""
        invalid_config = {
            'aws_region': 'us-east-1',
            'bedrock_model_id': 'some-model'
        }
        
        with pytest.raises(TypeError) as exc_info:
            SyntheticDataGenerator(mock_bedrock_client, invalid_config)
        
        assert "config must be a PipelineConfig instance" in str(exc_info.value)
        assert "dict" in str(exc_info.value)
    
    def test_init_with_string_config(self, mock_bedrock_client):
        """Test that string config raises TypeError"""
        with pytest.raises(TypeError) as exc_info:
            SyntheticDataGenerator(mock_bedrock_client, "not a config")
        
        assert "config must be a PipelineConfig instance" in str(exc_info.value)
        assert "str" in str(exc_info.value)
    
    def test_init_with_incomplete_config(self, mock_bedrock_client):
        """Test that config missing required attributes raises AttributeError"""
        # Create a mock object that passes isinstance check but lacks attributes
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        
        # Remove required attributes
        del incomplete_config.bedrock_model_id
        del incomplete_config.aws_region
        
        with pytest.raises(AttributeError) as exc_info:
            SyntheticDataGenerator(mock_bedrock_client, incomplete_config)
        
        error_msg = str(exc_info.value)
        assert "missing required attributes" in error_msg
        assert "bedrock_model_id" in error_msg
        assert "aws_region" in error_msg
    
    def test_init_with_config_missing_bedrock_model_id(self, mock_bedrock_client):
        """Test that config without bedrock_model_id raises AttributeError"""
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.max_retries = 3
        incomplete_config.initial_backoff_seconds = 2
        incomplete_config.max_backoff_seconds = 60
        # Missing bedrock_model_id
        
        with pytest.raises(AttributeError) as exc_info:
            SyntheticDataGenerator(mock_bedrock_client, incomplete_config)
        
        assert "bedrock_model_id" in str(exc_info.value)
    
    def test_init_with_config_missing_retry_params(self, mock_bedrock_client):
        """Test that config without retry parameters raises AttributeError"""
        # Create a mock that properly simulates missing attributes
        incomplete_config = Mock(spec=PipelineConfig)
        incomplete_config.__class__ = PipelineConfig
        
        # Set the attributes that exist
        incomplete_config.aws_region = "us-east-1"
        incomplete_config.bedrock_model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
        
        # Configure hasattr to return False for missing retry params
        def custom_hasattr(obj, name):
            if name in ['max_retries', 'initial_backoff_seconds', 'max_backoff_seconds']:
                return False
            return True
        
        # Patch hasattr for this test
        import builtins
        original_hasattr = builtins.hasattr
        builtins.hasattr = custom_hasattr
        
        try:
            with pytest.raises(AttributeError) as exc_info:
                SyntheticDataGenerator(mock_bedrock_client, incomplete_config)
            
            error_msg = str(exc_info.value)
            assert "max_retries" in error_msg or "initial_backoff_seconds" in error_msg
        finally:
            # Restore original hasattr
            builtins.hasattr = original_hasattr
    
    def test_init_with_different_model_ids(self, mock_bedrock_client):
        """Test initialization with different Bedrock model IDs"""
        model_ids = [
            "anthropic.claude-sonnet-4-20250514-v1:0",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-v2",
        ]
        
        for model_id in model_ids:
            config = PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id=model_id,
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-bucket"
            )
            
            generator = SyntheticDataGenerator(mock_bedrock_client, config)
            assert generator.model_id == model_id
    
    def test_init_with_different_regions(self, mock_bedrock_client):
        """Test initialization with different AWS regions"""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
        
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
                s3_bucket="my-bucket"
            )
            
            generator = SyntheticDataGenerator(mock_bedrock_client, config)
            assert generator.config.aws_region == region
    
    def test_init_with_different_retry_settings(self, mock_bedrock_client):
        """Test initialization with different retry configurations"""
        retry_configs = [
            {'max_retries': 1, 'initial_backoff_seconds': 1, 'max_backoff_seconds': 30},
            {'max_retries': 3, 'initial_backoff_seconds': 2, 'max_backoff_seconds': 60},
            {'max_retries': 5, 'initial_backoff_seconds': 5, 'max_backoff_seconds': 120},
        ]
        
        for retry_config in retry_configs:
            config = PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-bucket",
                **retry_config
            )
            
            generator = SyntheticDataGenerator(mock_bedrock_client, config)
            assert generator.config.max_retries == retry_config['max_retries']
            assert generator.config.initial_backoff_seconds == retry_config['initial_backoff_seconds']
            assert generator.config.max_backoff_seconds == retry_config['max_backoff_seconds']
    
    def test_init_does_not_modify_client(self, mock_bedrock_client, valid_pipeline_config):
        """Test that initialization doesn't modify the bedrock_client"""
        original_client = mock_bedrock_client
        
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        assert generator.bedrock_client is original_client
        # Verify client wasn't wrapped or modified
        assert type(generator.bedrock_client) == type(original_client)
    
    def test_init_does_not_modify_config(self, mock_bedrock_client, valid_pipeline_config):
        """Test that initialization doesn't modify the config"""
        original_model_id = valid_pipeline_config.bedrock_model_id
        original_region = valid_pipeline_config.aws_region
        
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        assert generator.config is valid_pipeline_config
        assert valid_pipeline_config.bedrock_model_id == original_model_id
        assert valid_pipeline_config.aws_region == original_region
    
    def test_init_multiple_instances_independent(self, valid_pipeline_config):
        """Test that multiple generator instances are independent"""
        client1 = Mock()
        client2 = Mock()
        
        generator1 = SyntheticDataGenerator(client1, valid_pipeline_config)
        generator2 = SyntheticDataGenerator(client2, valid_pipeline_config)
        
        assert generator1.bedrock_client is not generator2.bedrock_client
        assert generator1.bedrock_client is client1
        assert generator2.bedrock_client is client2
        # Config can be shared
        assert generator1.config is generator2.config
    
    def test_init_with_real_boto3_client_structure(self, valid_pipeline_config):
        """Test initialization with a mock that mimics real boto3 client structure"""
        # Create a more realistic mock that mimics boto3 client
        mock_client = MagicMock()
        mock_client._service_model = Mock()
        mock_client._service_model.service_name = 'bedrock-runtime'
        mock_client.invoke_model = Mock()
        mock_client.meta = Mock()
        mock_client.meta.region_name = 'us-east-1'
        
        generator = SyntheticDataGenerator(mock_client, valid_pipeline_config)
        
        assert generator.bedrock_client is mock_client
        assert generator.config is valid_pipeline_config
        assert generator.model_id == valid_pipeline_config.bedrock_model_id
    
    def test_init_logging(self, mock_bedrock_client, valid_pipeline_config, caplog):
        """Test that initialization logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        # Check that info log was created
        assert any("SyntheticDataGenerator initialized" in record.message 
                  for record in caplog.records)
    
    def test_init_sets_up_for_future_methods(self, mock_bedrock_client, valid_pipeline_config):
        """Test that __init__ properly sets up instance for future method calls"""
        generator = SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
        
        # Verify all necessary attributes are present for future methods
        assert hasattr(generator, 'bedrock_client')
        assert hasattr(generator, 'config')
        assert hasattr(generator, 'model_id')
        
        # Verify attributes are of correct types
        assert generator.config is valid_pipeline_config
        assert isinstance(generator.model_id, str)
        assert len(generator.model_id) > 0


class TestSyntheticDataGeneratorInitEdgeCases:
    """Test edge cases and boundary conditions for __init__"""
    
    def test_init_with_empty_model_id(self, mock_bedrock_client):
        """Test that empty bedrock_model_id in config raises error during PipelineConfig creation"""
        with pytest.raises(ValueError):
            config = PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id="",  # Empty string
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-bucket"
            )
    
    def test_init_with_whitespace_model_id(self, mock_bedrock_client):
        """Test that whitespace-only bedrock_model_id raises error during PipelineConfig creation"""
        with pytest.raises(ValueError):
            config = PipelineConfig(
                aws_region="us-east-1",
                bedrock_model_id="   ",  # Whitespace only
                sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
                training_instance_type="ml.g5.2xlarge",
                inference_instance_type="ml.g5.xlarge",
                baseline_model_endpoint="llama-70b-baseline",
                performance_threshold=0.60,
                max_iterations=5,
                cleanup_resources=True,
                s3_bucket="my-bucket"
            )
    
    def test_init_preserves_config_reference(self):
        """Test that the same config object can be used for multiple generators"""
        mock_client = Mock()
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="llama-70b-baseline",
            performance_threshold=0.60,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="my-bucket"
        )
        
        generator1 = SyntheticDataGenerator(mock_client, config)
        generator2 = SyntheticDataGenerator(mock_client, config)
        
        # Both should reference the same config object
        assert generator1.config is config
        assert generator2.config is config
        assert generator1.config is generator2.config


# Fixture for mock bedrock client at module level
@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock Runtime client"""
    mock_client = Mock()
    mock_client.invoke_model = Mock(return_value={
        'body': Mock(),
        'contentType': 'application/json'
    })
    return mock_client



class TestGenerateTrainingData:
    """Test suite for SyntheticDataGenerator.generate_training_data() method"""
    
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
    def valid_use_case(self):
        """Create a valid UseCase for testing"""
        from src.config_models import UseCase
        return UseCase(
            name="test_use_case",
            description="A test use case for customer support",
            test_questions=["Question 1", "Question 2"],
            judge_criteria="Evaluate based on helpfulness",
            data_generation_prompt="Generate helpful customer support examples",
            judge_prompt="Compare the responses"
        )
    
    @pytest.fixture
    def mock_bedrock_response(self):
        """Create a mock Bedrock response with training examples"""
        examples = [
            {
                "instruction": "Help a customer with a refund",
                "context": "Customer ordered wrong item",
                "response": "I'll process your refund immediately"
            },
            {
                "instruction": "Assist with shipping inquiry",
                "context": "Package is delayed",
                "response": "Let me check the tracking information"
            }
        ]
        
        # Mock the response structure
        mock_body = Mock()
        mock_body.read.return_value = json.dumps({
            'content': [{'text': json.dumps(examples)}]
        }).encode('utf-8')
        
        return {
            'body': mock_body,
            'contentType': 'application/json'
        }
    
    @pytest.fixture
    def generator_with_mock(self, mock_bedrock_client, valid_pipeline_config):
        """Create generator with mocked Bedrock client"""
        return SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
    
    def test_generate_training_data_basic(
        self, generator_with_mock, valid_use_case, mock_bedrock_response, tmp_path, monkeypatch
    ):
        """Test basic training data generation"""
        # Mock the output directory to use tmp_path
        monkeypatch.setattr('src.synthetic_data_generator.Path', lambda x: tmp_path / x)
        
        # Configure mock to return examples
        generator_with_mock.bedrock_client.invoke_model.return_value = mock_bedrock_response
        
        # Generate small dataset
        output_path = generator_with_mock.generate_training_data(
            valid_use_case,
            num_examples=4,
            batch_size=2
        )
        
        # Verify output path is returned
        assert output_path is not None
        assert isinstance(output_path, str)
        assert valid_use_case.name in output_path
        assert output_path.endswith('.jsonl')
    
    def test_generate_training_data_creates_file(
        self, generator_with_mock, valid_use_case, mock_bedrock_response, tmp_path, monkeypatch
    ):
        """Test that training data file is created"""
        import os
        
        # Create the output directory in tmp_path
        output_dir = tmp_path / "event_files" / "training_data"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Mock Path to use tmp_path
        original_path = Path
        
        def mock_path_constructor(path_str):
            if path_str == "event_files/training_data":
                return output_dir
            return original_path(path_str)
        
        monkeypatch.setattr('src.synthetic_data_generator.Path', mock_path_constructor)
        
        # Configure mock
        generator_with_mock.bedrock_client.invoke_model.return_value = mock_bedrock_response
        
        # Generate data
        output_path = generator_with_mock.generate_training_data(
            valid_use_case,
            num_examples=2,
            batch_size=2
        )
        
        # Verify file exists
        assert os.path.exists(output_path)
    
    def test_generate_training_data_validates_num_examples(
        self, generator_with_mock, valid_use_case
    ):
        """Test that num_examples must be positive"""
        with pytest.raises(ValueError) as exc_info:
            generator_with_mock.generate_training_data(
                valid_use_case,
                num_examples=0,
                batch_size=10
            )
        
        assert "num_examples must be positive" in str(exc_info.value)
    
    def test_generate_training_data_validates_negative_num_examples(
        self, generator_with_mock, valid_use_case
    ):
        """Test that negative num_examples raises error"""
        with pytest.raises(ValueError) as exc_info:
            generator_with_mock.generate_training_data(
                valid_use_case,
                num_examples=-5,
                batch_size=10
            )
        
        assert "num_examples must be positive" in str(exc_info.value)
    
    def test_generate_training_data_validates_batch_size(
        self, generator_with_mock, valid_use_case
    ):
        """Test that batch_size must be positive"""
        with pytest.raises(ValueError) as exc_info:
            generator_with_mock.generate_training_data(
                valid_use_case,
                num_examples=10,
                batch_size=0
            )
        
        assert "batch_size must be positive" in str(exc_info.value)
    
    def test_generate_training_data_validates_negative_batch_size(
        self, generator_with_mock, valid_use_case
    ):
        """Test that negative batch_size raises error"""
        with pytest.raises(ValueError) as exc_info:
            generator_with_mock.generate_training_data(
                valid_use_case,
                num_examples=10,
                batch_size=-2
            )
        
        assert "batch_size must be positive" in str(exc_info.value)
    
    def test_generate_training_data_calls_bedrock(
        self, generator_with_mock, valid_use_case, mock_bedrock_response, tmp_path, monkeypatch
    ):
        """Test that Bedrock API is called"""
        # Mock output directory
        output_dir = tmp_path / "event_files" / "training_data"
        output_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            'src.synthetic_data_generator.Path',
            lambda x: output_dir if x == "event_files/training_data" else Path(x)
        )
        
        # Configure mock
        generator_with_mock.bedrock_client.invoke_model.return_value = mock_bedrock_response
        
        # Generate data
        generator_with_mock.generate_training_data(
            valid_use_case,
            num_examples=2,
            batch_size=2
        )
        
        # Verify Bedrock was called
        assert generator_with_mock.bedrock_client.invoke_model.called
        assert generator_with_mock.bedrock_client.invoke_model.call_count >= 1
    
    def test_generate_training_data_batch_processing(
        self, generator_with_mock, valid_use_case, mock_bedrock_response, tmp_path, monkeypatch
    ):
        """Test that data is generated in batches"""
        # Mock output directory
        output_dir = tmp_path / "event_files" / "training_data"
        output_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            'src.synthetic_data_generator.Path',
            lambda x: output_dir if x == "event_files/training_data" else Path(x)
        )
        
        # Configure mock
        generator_with_mock.bedrock_client.invoke_model.return_value = mock_bedrock_response
        
        # Generate data with multiple batches
        generator_with_mock.generate_training_data(
            valid_use_case,
            num_examples=6,
            batch_size=2
        )
        
        # Should call Bedrock 3 times (6 examples / 2 per batch)
        assert generator_with_mock.bedrock_client.invoke_model.call_count == 3
    
    def test_generate_training_data_default_parameters(
        self, generator_with_mock, valid_use_case, mock_bedrock_response, tmp_path, monkeypatch
    ):
        """Test generation with default parameters"""
        # Mock output directory
        output_dir = tmp_path / "event_files" / "training_data"
        output_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            'src.synthetic_data_generator.Path',
            lambda x: output_dir if x == "event_files/training_data" else Path(x)
        )
        
        # Configure mock
        generator_with_mock.bedrock_client.invoke_model.return_value = mock_bedrock_response
        
        # Generate with defaults (num_examples=1000, batch_size=50)
        # We'll mock it to avoid generating 1000 examples
        output_path = generator_with_mock.generate_training_data(valid_use_case)
        
        # Should have been called (1000 / 50 = 20 times)
        assert generator_with_mock.bedrock_client.invoke_model.call_count == 20


class TestGenerateBatch:
    """Test suite for SyntheticDataGenerator._generate_batch() method"""
    
    @pytest.fixture
    def generator_with_mock(self, mock_bedrock_client, valid_pipeline_config):
        """Create generator with mocked Bedrock client"""
        return SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
    
    def test_generate_batch_returns_list(self, generator_with_mock):
        """Test that _generate_batch returns a list"""
        # Mock response
        mock_body = Mock()
        mock_body.read.return_value = json.dumps({
            'content': [{'text': json.dumps([
                {"instruction": "Test", "context": "Context", "response": "Response"}
            ])}]
        }).encode('utf-8')
        
        generator_with_mock.bedrock_client.invoke_model.return_value = {
            'body': mock_body
        }
        
        result = generator_with_mock._generate_batch(
            "Generate examples",
            "Test use case",
            1
        )
        
        assert isinstance(result, list)
    
    def test_generate_batch_returns_training_examples(self, generator_with_mock):
        """Test that _generate_batch returns TrainingExample objects"""
        from src.config_models import TrainingExample
        
        # Mock response
        mock_body = Mock()
        mock_body.read.return_value = json.dumps({
            'content': [{'text': json.dumps([
                {"instruction": "Test", "context": "Context", "response": "Response"}
            ])}]
        }).encode('utf-8')
        
        generator_with_mock.bedrock_client.invoke_model.return_value = {
            'body': mock_body
        }
        
        result = generator_with_mock._generate_batch(
            "Generate examples",
            "Test use case",
            1
        )
        
        assert len(result) > 0
        assert all(isinstance(ex, TrainingExample) for ex in result)
    
    def test_generate_batch_retry_on_failure(self, generator_with_mock):
        """Test that _generate_batch retries on failure"""
        # First call fails, second succeeds
        mock_body = Mock()
        mock_body.read.return_value = json.dumps({
            'content': [{'text': json.dumps([
                {"instruction": "Test", "context": "Context", "response": "Response"}
            ])}]
        }).encode('utf-8')
        
        generator_with_mock.bedrock_client.invoke_model.side_effect = [
            Exception("Transient error"),
            {'body': mock_body}
        ]
        
        result = generator_with_mock._generate_batch(
            "Generate examples",
            "Test use case",
            1
        )
        
        # Should succeed after retry
        assert len(result) > 0
        assert generator_with_mock.bedrock_client.invoke_model.call_count == 2
    
    def test_generate_batch_fails_after_max_retries(self, generator_with_mock):
        """Test that _generate_batch fails after max retries"""
        # All calls fail
        generator_with_mock.bedrock_client.invoke_model.side_effect = Exception("Persistent error")
        
        with pytest.raises(RuntimeError) as exc_info:
            generator_with_mock._generate_batch(
                "Generate examples",
                "Test use case",
                1
            )
        
        assert "Failed to generate batch" in str(exc_info.value)
        # Should have tried max_retries times (default 3)
        assert generator_with_mock.bedrock_client.invoke_model.call_count == 3
    
    def test_generate_batch_handles_markdown_wrapped_json(self, generator_with_mock):
        """Test that _generate_batch handles JSON wrapped in markdown code blocks"""
        # Mock response with markdown-wrapped JSON
        mock_body = Mock()
        json_content = json.dumps([
            {"instruction": "Test", "context": "Context", "response": "Response"}
        ])
        mock_body.read.return_value = json.dumps({
            'content': [{'text': f'```json\n{json_content}\n```'}]
        }).encode('utf-8')
        
        generator_with_mock.bedrock_client.invoke_model.return_value = {
            'body': mock_body
        }
        
        result = generator_with_mock._generate_batch(
            "Generate examples",
            "Test use case",
            1
        )
        
        assert len(result) > 0
    
    def test_generate_batch_cleans_unicode(self, generator_with_mock):
        """Test that _generate_batch cleans unicode characters"""
        # Mock response with unicode characters
        mock_body = Mock()
        mock_body.read.return_value = json.dumps({
            'content': [{'text': json.dumps([
                {"instruction": "Test café", "context": "Context", "response": "Response"}
            ])}]
        }).encode('utf-8')
        
        generator_with_mock.bedrock_client.invoke_model.return_value = {
            'body': mock_body
        }
        
        result = generator_with_mock._generate_batch(
            "Generate examples",
            "Test use case",
            1
        )
        
        # Unicode should be cleaned (café -> cafe)
        assert len(result) > 0
        # The é should be removed or converted
        assert 'é' not in result[0].instruction


class TestSaveProgress:
    """Test suite for SyntheticDataGenerator._save_progress() method"""
    
    @pytest.fixture
    def generator_with_mock(self, mock_bedrock_client, valid_pipeline_config):
        """Create generator with mocked Bedrock client"""
        return SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
    
    @pytest.fixture
    def sample_examples(self):
        """Create sample training examples"""
        from src.config_models import TrainingExample
        return [
            TrainingExample(
                instruction="Test instruction 1",
                context="Test context 1",
                response="Test response 1"
            ),
            TrainingExample(
                instruction="Test instruction 2",
                context="Test context 2",
                response="Test response 2"
            )
        ]
    
    def test_save_progress_creates_file(self, generator_with_mock, sample_examples, tmp_path):
        """Test that _save_progress creates output file"""
        output_path = tmp_path / "test_output.jsonl"
        
        generator_with_mock._save_progress(sample_examples, str(output_path))
        
        assert output_path.exists()
    
    def test_save_progress_writes_jsonl_format(self, generator_with_mock, sample_examples, tmp_path):
        """Test that _save_progress writes in JSONL format"""
        output_path = tmp_path / "test_output.jsonl"
        
        generator_with_mock._save_progress(sample_examples, str(output_path))
        
        # Read and verify format
        with open(output_path, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert 'instruction' in data
            assert 'context' in data
            assert 'response' in data
    
    def test_save_progress_appends_to_existing_file(self, generator_with_mock, sample_examples, tmp_path):
        """Test that _save_progress appends to existing file"""
        output_path = tmp_path / "test_output.jsonl"
        
        # Save first batch
        generator_with_mock._save_progress([sample_examples[0]], str(output_path))
        
        # Save second batch
        generator_with_mock._save_progress([sample_examples[1]], str(output_path))
        
        # Read and verify both are present
        with open(output_path, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
    
    def test_save_progress_handles_empty_list(self, generator_with_mock, tmp_path):
        """Test that _save_progress handles empty example list"""
        output_path = tmp_path / "test_output.jsonl"
        
        # Should not raise error
        generator_with_mock._save_progress([], str(output_path))
        
        # File should exist but be empty
        assert output_path.exists()
        with open(output_path, 'r') as f:
            content = f.read()
        assert content == ""


class TestCleanUnicode:
    """Test suite for SyntheticDataGenerator._clean_unicode() method"""
    
    @pytest.fixture
    def generator_with_mock(self, mock_bedrock_client, valid_pipeline_config):
        """Create generator with mocked Bedrock client"""
        return SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
    
    def test_clean_unicode_removes_accents(self, generator_with_mock):
        """Test that _clean_unicode removes accented characters"""
        text = "café résumé"
        result = generator_with_mock._clean_unicode(text)
        
        # Accents should be removed
        assert 'é' not in result
        assert 'cafe' in result or 'caf' in result
    
    def test_clean_unicode_handles_empty_string(self, generator_with_mock):
        """Test that _clean_unicode handles empty string"""
        result = generator_with_mock._clean_unicode("")
        assert result == ""
    
    def test_clean_unicode_handles_none(self, generator_with_mock):
        """Test that _clean_unicode handles None"""
        result = generator_with_mock._clean_unicode(None)
        assert result is None
    
    def test_clean_unicode_preserves_ascii(self, generator_with_mock):
        """Test that _clean_unicode preserves ASCII characters"""
        text = "Hello World 123"
        result = generator_with_mock._clean_unicode(text)
        assert result == text
    
    def test_clean_unicode_removes_emoji(self, generator_with_mock):
        """Test that _clean_unicode removes emoji"""
        text = "Hello 😀 World"
        result = generator_with_mock._clean_unicode(text)
        
        # Emoji should be removed
        assert '😀' not in result
        assert 'Hello' in result
        assert 'World' in result


# Import json for tests
import json
from pathlib import Path
from unittest.mock import Mock


# Module-level fixtures for reuse across test classes
@pytest.fixture
def valid_pipeline_config():
    """Create a valid PipelineConfig for testing"""
    from src.config_models import PipelineConfig
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




class TestAnalyzeDataset:
    """Test suite for SyntheticDataGenerator.analyze_dataset() method"""
    
    @pytest.fixture
    def generator_with_mock(self, mock_bedrock_client, valid_pipeline_config):
        """Create generator with mocked Bedrock client"""
        return SyntheticDataGenerator(mock_bedrock_client, valid_pipeline_config)
    
    @pytest.fixture
    def sample_dataset_small(self, tmp_path):
        """Create a small sample dataset (< 200 examples)"""
        dataset_path = tmp_path / "small_dataset.jsonl"
        examples = [
            {"instruction": "Test instruction 1", "context": "Context 1", "response": "Response 1"},
            {"instruction": "Test instruction 2", "context": "Context 2", "response": "Response 2"},
            {"instruction": "Test instruction 3", "context": "Context 3", "response": "Response 3"},
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        return str(dataset_path)
    
    @pytest.fixture
    def sample_dataset_medium(self, tmp_path):
        """Create a medium sample dataset (200-499 examples)"""
        dataset_path = tmp_path / "medium_dataset.jsonl"
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for i in range(250):
                example = {
                    "instruction": f"Test instruction {i}",
                    "context": f"Context {i}",
                    "response": f"Response {i}"
                }
                f.write(json.dumps(example) + '\n')
        
        return str(dataset_path)
    
    @pytest.fixture
    def sample_dataset_large(self, tmp_path):
        """Create a large sample dataset (>= 1000 examples)"""
        dataset_path = tmp_path / "large_dataset.jsonl"
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for i in range(1200):
                example = {
                    "instruction": f"Test instruction {i}",
                    "context": f"Context {i}",
                    "response": f"Response {i}"
                }
                f.write(json.dumps(example) + '\n')
        
        return str(dataset_path)
    
    def test_analyze_dataset_returns_dataset_analysis(self, generator_with_mock, sample_dataset_small):
        """Test that analyze_dataset returns a DatasetAnalysis object"""
        from src.config_models import DatasetAnalysis
        
        result = generator_with_mock.analyze_dataset(sample_dataset_small)
        
        assert isinstance(result, DatasetAnalysis)
    
    def test_analyze_dataset_counts_examples_correctly(self, generator_with_mock, sample_dataset_small):
        """Test that analyze_dataset counts examples correctly"""
        result = generator_with_mock.analyze_dataset(sample_dataset_small)
        
        assert result.num_examples == 3
    
    def test_analyze_dataset_calculates_avg_instruction_length(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset calculates average instruction length"""
        dataset_path = tmp_path / "test_dataset.jsonl"
        examples = [
            {"instruction": "Short", "context": "", "response": "Response"},  # 5 chars
            {"instruction": "Medium length", "context": "", "response": "Response"},  # 13 chars
            {"instruction": "A much longer instruction", "context": "", "response": "Response"},  # 25 chars
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Average should be (5 + 13 + 25) / 3 = 43 / 3 = 14 (integer division)
        assert result.avg_instruction_length == 14
    
    def test_analyze_dataset_calculates_avg_response_length(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset calculates average response length"""
        dataset_path = tmp_path / "test_dataset.jsonl"
        examples = [
            {"instruction": "Test", "context": "", "response": "Short"},  # 5 chars
            {"instruction": "Test", "context": "", "response": "Medium response"},  # 15 chars
            {"instruction": "Test", "context": "", "response": "A much longer response here"},  # 27 chars
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Average should be (5 + 15 + 27) / 3 = 47 / 3 = 15 (integer division)
        assert result.avg_response_length == 15
    
    def test_analyze_dataset_recommends_parameters_for_small_dataset(self, generator_with_mock, sample_dataset_small):
        """Test that small datasets get appropriate recommendations"""
        result = generator_with_mock.analyze_dataset(sample_dataset_small)
        
        # Small dataset (< 200): more epochs, smaller batch size
        assert result.recommended_epochs == 10
        assert result.recommended_batch_size == 4
    
    def test_analyze_dataset_recommends_parameters_for_medium_dataset(self, generator_with_mock, sample_dataset_medium):
        """Test that medium datasets get appropriate recommendations"""
        result = generator_with_mock.analyze_dataset(sample_dataset_medium)
        
        # Medium dataset (200-499): medium epochs, medium batch size
        assert result.recommended_epochs == 7
        assert result.recommended_batch_size == 8
    
    def test_analyze_dataset_recommends_parameters_for_large_dataset(self, generator_with_mock, sample_dataset_large):
        """Test that large datasets get appropriate recommendations"""
        result = generator_with_mock.analyze_dataset(sample_dataset_large)
        
        # Large dataset (>= 1000): fewer epochs, larger batch size
        assert result.recommended_epochs == 3
        assert result.recommended_batch_size == 32
    
    def test_analyze_dataset_batch_sizes_are_powers_of_2(self, generator_with_mock, tmp_path):
        """Test that recommended batch sizes are always powers of 2"""
        # Test various dataset sizes
        dataset_sizes = [50, 250, 600, 1500]
        
        for size in dataset_sizes:
            dataset_path = tmp_path / f"dataset_{size}.jsonl"
            
            with open(dataset_path, 'w', encoding='utf-8') as f:
                for i in range(size):
                    example = {
                        "instruction": f"Test {i}",
                        "context": "",
                        "response": f"Response {i}"
                    }
                    f.write(json.dumps(example) + '\n')
            
            result = generator_with_mock.analyze_dataset(str(dataset_path))
            
            # Check that batch size is a power of 2
            batch_size = result.recommended_batch_size
            assert batch_size > 0
            assert (batch_size & (batch_size - 1)) == 0, f"Batch size {batch_size} is not a power of 2"
    
    def test_analyze_dataset_raises_error_for_nonexistent_file(self, generator_with_mock):
        """Test that analyze_dataset raises FileNotFoundError for nonexistent file"""
        with pytest.raises(FileNotFoundError) as exc_info:
            generator_with_mock.analyze_dataset("/nonexistent/path/dataset.jsonl")
        
        assert "Dataset file not found" in str(exc_info.value)
    
    def test_analyze_dataset_raises_error_for_empty_file(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset raises ValueError for empty file"""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.touch()
        
        with pytest.raises(ValueError) as exc_info:
            generator_with_mock.analyze_dataset(str(empty_file))
        
        assert "empty or contains no valid examples" in str(exc_info.value)
    
    def test_analyze_dataset_skips_invalid_json_lines(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset skips lines with invalid JSON"""
        dataset_path = tmp_path / "mixed_dataset.jsonl"
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps({"instruction": "Valid 1", "context": "", "response": "Response 1"}) + '\n')
            f.write("This is not valid JSON\n")
            f.write(json.dumps({"instruction": "Valid 2", "context": "", "response": "Response 2"}) + '\n')
            f.write("{invalid json}\n")
            f.write(json.dumps({"instruction": "Valid 3", "context": "", "response": "Response 3"}) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Should count only the 3 valid examples
        assert result.num_examples == 3
    
    def test_analyze_dataset_skips_lines_missing_instruction(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset skips lines missing instruction field"""
        dataset_path = tmp_path / "incomplete_dataset.jsonl"
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps({"instruction": "Valid", "context": "", "response": "Response"}) + '\n')
            f.write(json.dumps({"context": "No instruction", "response": "Response"}) + '\n')
            f.write(json.dumps({"instruction": "Valid 2", "context": "", "response": "Response 2"}) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Should count only the 2 valid examples
        assert result.num_examples == 2
    
    def test_analyze_dataset_skips_lines_missing_response(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset skips lines missing response field"""
        dataset_path = tmp_path / "incomplete_dataset.jsonl"
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps({"instruction": "Valid", "context": "", "response": "Response"}) + '\n')
            f.write(json.dumps({"instruction": "No response", "context": "Context"}) + '\n')
            f.write(json.dumps({"instruction": "Valid 2", "context": "", "response": "Response 2"}) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Should count only the 2 valid examples
        assert result.num_examples == 2
    
    def test_analyze_dataset_skips_empty_lines(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset skips empty lines"""
        dataset_path = tmp_path / "dataset_with_empty_lines.jsonl"
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps({"instruction": "Test 1", "context": "", "response": "Response 1"}) + '\n')
            f.write('\n')  # Empty line
            f.write(json.dumps({"instruction": "Test 2", "context": "", "response": "Response 2"}) + '\n')
            f.write('   \n')  # Whitespace-only line
            f.write(json.dumps({"instruction": "Test 3", "context": "", "response": "Response 3"}) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Should count only the 3 valid examples
        assert result.num_examples == 3
    
    def test_analyze_dataset_handles_unicode_in_examples(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset handles unicode characters in examples"""
        dataset_path = tmp_path / "unicode_dataset.jsonl"
        examples = [
            {"instruction": "Test café", "context": "", "response": "Response with émojis 😀"},
            {"instruction": "Test résumé", "context": "", "response": "Response naïve"},
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Should successfully analyze despite unicode
        assert result.num_examples == 2
        assert result.avg_instruction_length > 0
        assert result.avg_response_length > 0
    
    def test_analyze_dataset_handles_very_long_examples(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset handles very long instruction/response texts"""
        dataset_path = tmp_path / "long_dataset.jsonl"
        
        long_instruction = "A" * 5000  # 5000 character instruction
        long_response = "B" * 10000  # 10000 character response
        
        examples = [
            {"instruction": long_instruction, "context": "", "response": long_response},
            {"instruction": "Short", "context": "", "response": "Short"},
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        assert result.num_examples == 2
        # Average should be (5000 + 5) / 2 = 2502
        assert result.avg_instruction_length == 2502
        # Average should be (10000 + 5) / 2 = 5002
        assert result.avg_response_length == 5002
    
    def test_analyze_dataset_handles_empty_instruction_or_response(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset handles empty instruction or response strings"""
        dataset_path = tmp_path / "empty_fields_dataset.jsonl"
        examples = [
            {"instruction": "", "context": "", "response": "Response"},
            {"instruction": "Instruction", "context": "", "response": ""},
            {"instruction": "Valid", "context": "", "response": "Valid response"},
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # All examples have the required fields (even if empty), so all should be counted
        assert result.num_examples == 3
        # Averages should account for empty strings (length 0)
        assert result.avg_instruction_length >= 0
        assert result.avg_response_length >= 0
    
    def test_analyze_dataset_context_field_optional(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset works when context field is missing"""
        dataset_path = tmp_path / "no_context_dataset.jsonl"
        examples = [
            {"instruction": "Test 1", "response": "Response 1"},
            {"instruction": "Test 2", "response": "Response 2"},
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        # Should work fine without context field
        assert result.num_examples == 2
    
    def test_analyze_dataset_recommendations_at_boundaries(self, generator_with_mock, tmp_path):
        """Test recommendations at exact boundary values"""
        # Test at exact boundaries: 200, 500, 1000
        boundaries = [
            (199, 10, 4),   # Just below 200
            (200, 7, 8),    # Exactly 200
            (499, 7, 8),    # Just below 500
            (500, 5, 16),   # Exactly 500
            (999, 5, 16),   # Just below 1000
            (1000, 3, 32),  # Exactly 1000
        ]
        
        for size, expected_epochs, expected_batch_size in boundaries:
            dataset_path = tmp_path / f"boundary_dataset_{size}.jsonl"
            
            with open(dataset_path, 'w', encoding='utf-8') as f:
                for i in range(size):
                    example = {
                        "instruction": f"Test {i}",
                        "context": "",
                        "response": f"Response {i}"
                    }
                    f.write(json.dumps(example) + '\n')
            
            result = generator_with_mock.analyze_dataset(str(dataset_path))
            
            assert result.num_examples == size
            assert result.recommended_epochs == expected_epochs, \
                f"For size {size}, expected {expected_epochs} epochs, got {result.recommended_epochs}"
            assert result.recommended_batch_size == expected_batch_size, \
                f"For size {size}, expected batch size {expected_batch_size}, got {result.recommended_batch_size}"
    
    def test_analyze_dataset_logging(self, generator_with_mock, sample_dataset_small, caplog):
        """Test that analyze_dataset logs appropriate messages"""
        import logging
        caplog.set_level(logging.INFO)
        
        result = generator_with_mock.analyze_dataset(sample_dataset_small)
        
        # Check that info logs were created
        assert any("Starting dataset analysis" in record.message for record in caplog.records)
        assert any("Dataset analysis completed" in record.message for record in caplog.records)
    
    def test_analyze_dataset_with_real_training_data_format(self, generator_with_mock, tmp_path):
        """Test analyze_dataset with realistic training data format"""
        dataset_path = tmp_path / "realistic_dataset.jsonl"
        examples = [
            {
                "instruction": "Respond to this customer inquiry about a delayed order",
                "context": "Customer says: My order #12345 hasn't arrived yet and it's been 2 weeks",
                "response": "I sincerely apologize for the delay with your order #12345. Let me check the tracking information for you right away. I can see that there was an unexpected delay at our distribution center. I'll expedite your order and ensure it arrives within 2 business days. Additionally, I'd like to offer you a 20% discount on your next purchase as an apology for this inconvenience."
            },
            {
                "instruction": "Help a customer with a product return",
                "context": "Customer received a damaged item",
                "response": "I'm very sorry to hear that your item arrived damaged. We'll make this right immediately. I'm processing a full refund to your original payment method, which should appear within 3-5 business days. I'm also sending you a prepaid return label via email so you can return the damaged item at no cost to you."
            },
        ]
        
        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        result = generator_with_mock.analyze_dataset(str(dataset_path))
        
        assert result.num_examples == 2
        assert result.avg_instruction_length > 0
        assert result.avg_response_length > 0
        assert result.recommended_epochs > 0
        assert result.recommended_batch_size > 0
    
    def test_analyze_dataset_returns_valid_dataset_analysis_object(self, generator_with_mock, sample_dataset_small):
        """Test that returned DatasetAnalysis object passes validation"""
        result = generator_with_mock.analyze_dataset(sample_dataset_small)
        
        # DatasetAnalysis __post_init__ validates these constraints
        assert result.num_examples >= 0
        assert result.recommended_epochs >= 1
        assert result.recommended_batch_size >= 1
    
    def test_analyze_dataset_handles_file_read_errors(self, generator_with_mock, tmp_path):
        """Test that analyze_dataset handles file read errors gracefully"""
        import sys
        
        # This test is platform-dependent and may not work on Windows
        if sys.platform == 'win32':
            pytest.skip("File permission tests don't work reliably on Windows")
        
        # Create a file and then make it unreadable
        dataset_path = tmp_path / "unreadable.jsonl"
        dataset_path.touch()
        
        # Try to make it unreadable
        import os
        try:
            os.chmod(dataset_path, 0o000)
            
            with pytest.raises((IOError, PermissionError, ValueError)):
                generator_with_mock.analyze_dataset(str(dataset_path))
        finally:
            # Restore permissions for cleanup
            os.chmod(dataset_path, 0o644)
    
    def test_analyze_dataset_multiple_calls_independent(self, generator_with_mock, tmp_path):
        """Test that multiple analyze_dataset calls are independent"""
        # Create two different datasets
        dataset1_path = tmp_path / "dataset1.jsonl"
        with open(dataset1_path, 'w', encoding='utf-8') as f:
            for i in range(100):
                f.write(json.dumps({"instruction": f"Test {i}", "context": "", "response": f"Response {i}"}) + '\n')
        
        dataset2_path = tmp_path / "dataset2.jsonl"
        with open(dataset2_path, 'w', encoding='utf-8') as f:
            for i in range(600):
                f.write(json.dumps({"instruction": f"Test {i}", "context": "", "response": f"Response {i}"}) + '\n')
        
        # Analyze both
        result1 = generator_with_mock.analyze_dataset(str(dataset1_path))
        result2 = generator_with_mock.analyze_dataset(str(dataset2_path))
        
        # Results should be different and independent
        assert result1.num_examples == 100
        assert result2.num_examples == 600
        assert result1.recommended_epochs != result2.recommended_epochs
        assert result1.recommended_batch_size != result2.recommended_batch_size
