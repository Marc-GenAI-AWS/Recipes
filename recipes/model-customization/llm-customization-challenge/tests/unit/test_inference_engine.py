"""
Unit tests for InferenceEngine class.

Tests cover:
- __init__ method with valid and invalid parameters
- SageMaker runtime client initialization
- Configuration validation
- Error handling for missing or invalid inputs
- generate_responses() method with various scenarios
- _invoke_endpoint() with retry logic
- _format_prompt() for model-specific formatting
- _clean_response() for response normalization
- Transient error detection and retry behavior
- Edge cases (empty questions, malformed responses, etc.)
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from io import BytesIO

from src.inference_engine import InferenceEngine
from src.config_models import PipelineConfig, ResponsePair, ResponsePairs


class TestInferenceEngineInit:
    """Test suite for InferenceEngine.__init__ method"""
    
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
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation
        mock_response_body = json.dumps([{"generated_text": "This is a test response"}])
        mock_response = {
            'Body': BytesIO(mock_response_body.encode('utf-8')),
            'ContentType': 'application/json'
        }
        mock_client.invoke_endpoint = Mock(return_value=mock_response)
        
        return mock_client
    
    def test_init_with_valid_parameters(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test initialization with valid sagemaker_runtime_client and config"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        assert engine.sagemaker_runtime_client is mock_sagemaker_runtime_client
        assert engine.config is valid_pipeline_config
    
    def test_init_stores_sagemaker_runtime_client(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that sagemaker_runtime_client is properly stored"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        assert hasattr(engine, 'sagemaker_runtime_client')
        assert engine.sagemaker_runtime_client is mock_sagemaker_runtime_client
    
    def test_init_stores_config(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that config is properly stored"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        assert hasattr(engine, 'config')
        assert engine.config is valid_pipeline_config
    
    def test_init_with_none_sagemaker_runtime_client(self, valid_pipeline_config):
        """Test that None sagemaker_runtime_client raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            InferenceEngine(None, valid_pipeline_config)
        
        assert "sagemaker_runtime_client cannot be None" in str(exc_info.value)
    
    def test_init_with_none_config(self, mock_sagemaker_runtime_client):
        """Test that None config raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            InferenceEngine(mock_sagemaker_runtime_client, None)
        
        assert "config cannot be None" in str(exc_info.value)


class TestGenerateResponses:
    """Test suite for InferenceEngine.generate_responses() method"""
    
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
            s3_bucket="my-finetuning-bucket"
        )
    
    @pytest.fixture
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client with successful responses"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "This is a test response"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        
        return mock_client
    
    def test_generate_responses_with_single_question(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test generating responses for a single question"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        questions = ["What is the capital of France?"]
        result = engine.generate_responses(
            questions=questions,
            finetuned_endpoint="test-finetuned-endpoint",
            baseline_endpoint="test-baseline-endpoint"
        )
        
        assert isinstance(result, ResponsePairs)
        assert len(result.pairs) == 1
        assert result.pairs[0].question == questions[0]
        assert result.finetuned_endpoint == "test-finetuned-endpoint"
        assert result.baseline_endpoint == "test-baseline-endpoint"
    
    def test_generate_responses_with_multiple_questions(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test generating responses for multiple questions"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        questions = [
            "What is the capital of France?",
            "What is 2 + 2?",
            "Who wrote Romeo and Juliet?"
        ]
        result = engine.generate_responses(
            questions=questions,
            finetuned_endpoint="test-finetuned-endpoint",
            baseline_endpoint="test-baseline-endpoint"
        )
        
        assert isinstance(result, ResponsePairs)
        assert len(result.pairs) == 3
        for i, pair in enumerate(result.pairs):
            assert pair.question == questions[i]
            assert isinstance(pair.finetuned_response, str)
            assert isinstance(pair.baseline_response, str)
    
    def test_generate_responses_uses_config_baseline_endpoint(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that config baseline endpoint is used when not provided"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        questions = ["Test question"]
        result = engine.generate_responses(
            questions=questions,
            finetuned_endpoint="test-finetuned-endpoint"
        )
        
        assert result.baseline_endpoint == valid_pipeline_config.baseline_model_endpoint
    
    def test_generate_responses_with_empty_questions_raises_error(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that empty questions list raises ValueError"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            engine.generate_responses(
                questions=[],
                finetuned_endpoint="test-finetuned-endpoint"
            )
        
        assert "questions list cannot be empty" in str(exc_info.value)
    
    def test_generate_responses_with_empty_finetuned_endpoint_raises_error(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that empty finetuned_endpoint raises ValueError"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            engine.generate_responses(
                questions=["Test question"],
                finetuned_endpoint=""
            )
        
        assert "finetuned_endpoint cannot be empty" in str(exc_info.value)
    
    def test_generate_responses_with_empty_baseline_endpoint_raises_error(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that empty baseline_endpoint raises ValueError"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        with pytest.raises(ValueError) as exc_info:
            engine.generate_responses(
                questions=["Test question"],
                finetuned_endpoint="test-finetuned-endpoint",
                baseline_endpoint=""
            )
        
        assert "baseline_endpoint cannot be empty" in str(exc_info.value)
    
    def test_generate_responses_invokes_both_endpoints(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that both finetuned and baseline endpoints are invoked"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        questions = ["Test question"]
        engine.generate_responses(
            questions=questions,
            finetuned_endpoint="test-finetuned-endpoint",
            baseline_endpoint="test-baseline-endpoint"
        )
        
        # Should be called twice per question (once for finetuned, once for baseline)
        assert mock_sagemaker_runtime_client.invoke_endpoint.call_count == 2
    
    def test_generate_responses_cleans_responses(self, valid_pipeline_config):
        """Test that responses are cleaned"""
        # Create a fresh mock for this test with custom response
        mock_client = Mock()
        
        # Mock response with special tokens and extra whitespace - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "<|begin_of_text|>Test  response<|end_of_text|>"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        
        engine = InferenceEngine(mock_client, valid_pipeline_config)
        
        questions = ["Test question"]
        result = engine.generate_responses(
            questions=questions,
            finetuned_endpoint="test-finetuned-endpoint",
            baseline_endpoint="test-baseline-endpoint"
        )
        
        # Check that special tokens are removed and whitespace is normalized
        assert "<|begin_of_text|>" not in result.pairs[0].finetuned_response
        assert "<|end_of_text|>" not in result.pairs[0].finetuned_response
        assert "Test response" in result.pairs[0].finetuned_response


class TestInvokeEndpoint:
    """Test suite for InferenceEngine._invoke_endpoint() method"""
    
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
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60
        )
    
    @pytest.fixture
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "Test response"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        return mock_client
    
    def test_invoke_endpoint_success(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test successful endpoint invocation"""
        mock_response_body = json.dumps([{"generated_text": "Test response"}])
        mock_response = {
            'Body': BytesIO(mock_response_body.encode('utf-8')),
            'ContentType': 'application/json'
        }
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(return_value=mock_response)
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        result = engine._invoke_endpoint("test-endpoint", "Test prompt")
        
        assert result == "Test response"
        assert mock_sagemaker_runtime_client.invoke_endpoint.call_count == 1
    
    def test_invoke_endpoint_with_dict_response(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test endpoint invocation with dict response format"""
        mock_response_body = json.dumps({"generated_text": "Test response"})
        mock_response = {
            'Body': BytesIO(mock_response_body.encode('utf-8')),
            'ContentType': 'application/json'
        }
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(return_value=mock_response)
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        result = engine._invoke_endpoint("test-endpoint", "Test prompt")
        
        assert result == "Test response"
    
    def test_invoke_endpoint_with_outputs_key(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test endpoint invocation with 'outputs' key in response"""
        mock_response_body = json.dumps({"outputs": "Test response"})
        mock_response = {
            'Body': BytesIO(mock_response_body.encode('utf-8')),
            'ContentType': 'application/json'
        }
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(return_value=mock_response)
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        result = engine._invoke_endpoint("test-endpoint", "Test prompt")
        
        assert result == "Test response"
    
    def test_invoke_endpoint_retry_on_transient_error(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that transient errors trigger retry"""
        # First call fails with throttling, second succeeds
        mock_response_body = json.dumps([{"generated_text": "Test response"}])
        mock_response = {
            'Body': BytesIO(mock_response_body.encode('utf-8')),
            'ContentType': 'application/json'
        }
        
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(
            side_effect=[
                Exception("ThrottlingException: Rate exceeded"),
                mock_response
            ]
        )
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = engine._invoke_endpoint("test-endpoint", "Test prompt", max_retries=3)
        
        assert result == "Test response"
        assert mock_sagemaker_runtime_client.invoke_endpoint.call_count == 2
    
    def test_invoke_endpoint_fails_after_max_retries(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that endpoint invocation fails after max retries"""
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(
            side_effect=Exception("ThrottlingException: Rate exceeded")
        )
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(RuntimeError) as exc_info:
                engine._invoke_endpoint("test-endpoint", "Test prompt", max_retries=3)
        
        assert "Failed to invoke endpoint" in str(exc_info.value)
        assert mock_sagemaker_runtime_client.invoke_endpoint.call_count == 3
    
    def test_invoke_endpoint_no_retry_on_non_transient_error(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that non-transient errors don't trigger retry"""
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(
            side_effect=Exception("ValidationException: Invalid input")
        )
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        with pytest.raises(RuntimeError) as exc_info:
            engine._invoke_endpoint("test-endpoint", "Test prompt", max_retries=3)
        
        assert "Failed to invoke endpoint" in str(exc_info.value)
        # Should only try once for non-transient errors
        assert mock_sagemaker_runtime_client.invoke_endpoint.call_count == 1
    
    def test_invoke_endpoint_sends_correct_payload(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that endpoint invocation sends correct payload"""
        mock_response_body = json.dumps([{"generated_text": "Test response"}])
        mock_response = {
            'Body': BytesIO(mock_response_body.encode('utf-8')),
            'ContentType': 'application/json'
        }
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(return_value=mock_response)
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        engine._invoke_endpoint("test-endpoint", "Test prompt")
        
        # Check that invoke_endpoint was called with correct parameters
        call_args = mock_sagemaker_runtime_client.invoke_endpoint.call_args
        assert call_args[1]['EndpointName'] == "test-endpoint"
        assert call_args[1]['ContentType'] == "application/json"
        
        # Check payload structure
        payload = json.loads(call_args[1]['Body'])
        assert 'inputs' in payload
        assert 'parameters' in payload
        assert payload['inputs'] == "Test prompt"



class TestFormatPrompt:
    """Test suite for InferenceEngine._format_prompt() method"""
    
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
            s3_bucket="my-finetuning-bucket"
        )
    
    @pytest.fixture
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "Test response"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        return mock_client
    
    def test_format_prompt_includes_question(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that formatted prompt includes the question"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        question = "What is the capital of France?"
        result = engine._format_prompt(question)
        
        assert question in result
    
    def test_format_prompt_uses_llama_format(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that formatted prompt uses Llama instruction format"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        question = "Test question"
        result = engine._format_prompt(question)
        
        # Check for Llama format markers
        assert "<|begin_of_text|>" in result
        assert "<|start_header_id|>user<|end_header_id|>" in result
        assert "<|eot_id|>" in result
        assert "<|start_header_id|>assistant<|end_header_id|>" in result
    
    def test_format_prompt_with_empty_question(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test formatting with empty question"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        result = engine._format_prompt("")
        
        # Should still return valid format structure
        assert "<|begin_of_text|>" in result
        assert "<|start_header_id|>" in result
    
    def test_format_prompt_with_special_characters(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test formatting with special characters in question"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        question = "What is 2 + 2? And what about 3 * 3?"
        result = engine._format_prompt(question)
        
        assert question in result
        assert "2 + 2" in result
        assert "3 * 3" in result


class TestCleanResponse:
    """Test suite for InferenceEngine._clean_response() method"""
    
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
            s3_bucket="my-finetuning-bucket"
        )
    
    @pytest.fixture
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "Test response"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        return mock_client
    
    def test_clean_response_removes_special_tokens(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that special tokens are removed"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        response = "<|begin_of_text|>Test response<|end_of_text|>"
        result = engine._clean_response(response)
        
        assert "<|begin_of_text|>" not in result
        assert "<|end_of_text|>" not in result
        assert "Test response" in result
    
    def test_clean_response_normalizes_whitespace(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that whitespace is normalized"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        response = "Test  response   with    extra     spaces"
        result = engine._clean_response(response)
        
        # Multiple spaces should be reduced to single space
        assert "  " not in result
        assert "Test response with extra spaces" == result
    
    def test_clean_response_normalizes_newlines(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that multiple newlines are normalized"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        response = "Line 1\n\n\n\nLine 2"
        result = engine._clean_response(response)
        
        # Multiple newlines should be reduced to double newline
        assert "\n\n\n" not in result
        assert "Line 1\n\nLine 2" == result
    
    def test_clean_response_trims_whitespace(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that leading/trailing whitespace is trimmed"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        response = "   Test response   "
        result = engine._clean_response(response)
        
        assert result == "Test response"
        assert not result.startswith(" ")
        assert not result.endswith(" ")
    
    def test_clean_response_with_empty_string(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test cleaning empty string"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        result = engine._clean_response("")
        
        assert result == ""
    
    def test_clean_response_normalizes_unicode(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that unicode is normalized"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        # Unicode with combining characters
        response = "café"  # Using combining accent
        result = engine._clean_response(response)
        
        # Should be normalized to NFC form
        assert isinstance(result, str)
        assert "caf" in result
    
    def test_clean_response_removes_all_special_tokens(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that all special tokens are removed"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        response = (
            "<|begin_of_text|><|start_header_id|>assistant<|end_header_id|>"
            "Test response<|eot_id|><|end_of_text|>"
        )
        result = engine._clean_response(response)
        
        # All special tokens should be removed
        assert "<|" not in result
        assert "|>" not in result
        # The word "assistant" between tags should also be removed as part of the header
        assert result.strip() == "Test response"


class TestIsTransientError:
    """Test suite for InferenceEngine._is_transient_error() method"""
    
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
            s3_bucket="my-finetuning-bucket"
        )
    
    @pytest.fixture
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "Test response"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        return mock_client
    
    def test_is_transient_error_throttling(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that throttling errors are identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("ThrottlingException: Rate exceeded")
        assert engine._is_transient_error(error) is True
    
    def test_is_transient_error_rate_exceeded(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that rate exceeded errors are identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("Rate exceeded")
        assert engine._is_transient_error(error) is True
    
    def test_is_transient_error_timeout(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that timeout errors are identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("Request timed out")
        assert engine._is_transient_error(error) is True
    
    def test_is_transient_error_connection(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that connection errors are identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("Connection error")
        assert engine._is_transient_error(error) is True
    
    def test_is_transient_error_service_unavailable(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that service unavailable errors are identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("Service unavailable")
        assert engine._is_transient_error(error) is True
    
    def test_is_transient_error_500(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that 500 errors are identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("500 Internal Server Error")
        assert engine._is_transient_error(error) is True
    
    def test_is_transient_error_503(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that 503 errors are identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("503 Service Unavailable")
        assert engine._is_transient_error(error) is True
    
    def test_is_not_transient_error_validation(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that validation errors are not identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("ValidationException: Invalid input")
        assert engine._is_transient_error(error) is False
    
    def test_is_not_transient_error_not_found(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that not found errors are not identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("ResourceNotFoundException: Endpoint not found")
        assert engine._is_transient_error(error) is False
    
    def test_is_not_transient_error_generic(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that generic errors are not identified as transient"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        error = Exception("Some random error")
        assert engine._is_transient_error(error) is False


class TestCalculateBackoff:
    """Test suite for InferenceEngine._calculate_backoff() method"""
    
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
            initial_backoff_seconds=2,
            max_backoff_seconds=60
        )
    
    @pytest.fixture
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "Test response"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        return mock_client
    
    def test_calculate_backoff_first_attempt(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test backoff calculation for first attempt"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        backoff = engine._calculate_backoff(0)
        
        assert backoff == 2  # initial_backoff_seconds
    
    def test_calculate_backoff_second_attempt(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test backoff calculation for second attempt"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        backoff = engine._calculate_backoff(1)
        
        assert backoff == 4  # 2 * 2^1
    
    def test_calculate_backoff_third_attempt(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test backoff calculation for third attempt"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        backoff = engine._calculate_backoff(2)
        
        assert backoff == 8  # 2 * 2^2
    
    def test_calculate_backoff_respects_max(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that backoff respects maximum"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        # Large attempt number should be capped at max_backoff_seconds
        backoff = engine._calculate_backoff(10)
        
        assert backoff == 60  # max_backoff_seconds
    
    def test_calculate_backoff_exponential_growth(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test that backoff grows exponentially"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        backoff_0 = engine._calculate_backoff(0)
        backoff_1 = engine._calculate_backoff(1)
        backoff_2 = engine._calculate_backoff(2)
        
        # Each backoff should be approximately double the previous
        assert backoff_1 == backoff_0 * 2
        assert backoff_2 == backoff_1 * 2


class TestEdgeCases:
    """Test suite for edge cases and error scenarios"""
    
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
            s3_bucket="my-finetuning-bucket"
        )
    
    @pytest.fixture
    def mock_sagemaker_runtime_client(self):
        """Create a mock SageMaker Runtime client"""
        mock_client = Mock()
        
        # Mock successful endpoint invocation - create new BytesIO for each call
        def create_response(*args, **kwargs):
            mock_response_body = json.dumps([{"generated_text": "Test response"}])
            return {
                'Body': BytesIO(mock_response_body.encode('utf-8')),
                'ContentType': 'application/json'
            }
        
        mock_client.invoke_endpoint = Mock(side_effect=create_response)
        return mock_client
    
    def test_generate_responses_with_very_long_question(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test generating responses for very long question"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        # Create a very long question
        long_question = "What is " + "very " * 1000 + "long question?"
        questions = [long_question]
        
        result = engine.generate_responses(
            questions=questions,
            finetuned_endpoint="test-finetuned-endpoint",
            baseline_endpoint="test-baseline-endpoint"
        )
        
        assert len(result.pairs) == 1
        assert result.pairs[0].question == long_question
    
    def test_generate_responses_with_unicode_question(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test generating responses for question with unicode characters"""
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        questions = ["What is the meaning of 日本語?"]
        result = engine.generate_responses(
            questions=questions,
            finetuned_endpoint="test-finetuned-endpoint",
            baseline_endpoint="test-baseline-endpoint"
        )
        
        assert len(result.pairs) == 1
        assert "日本語" in result.pairs[0].question
    
    def test_invoke_endpoint_with_malformed_json_response(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test handling of malformed JSON response"""
        mock_response = {
            'Body': BytesIO(b"Not valid JSON"),
            'ContentType': 'application/json'
        }
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(return_value=mock_response)
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        with pytest.raises(RuntimeError):
            engine._invoke_endpoint("test-endpoint", "Test prompt")
    
    def test_invoke_endpoint_with_empty_response(self, mock_sagemaker_runtime_client, valid_pipeline_config):
        """Test handling of empty response"""
        mock_response_body = json.dumps([{"generated_text": ""}])
        mock_response = {
            'Body': BytesIO(mock_response_body.encode('utf-8')),
            'ContentType': 'application/json'
        }
        mock_sagemaker_runtime_client.invoke_endpoint = Mock(return_value=mock_response)
        
        engine = InferenceEngine(mock_sagemaker_runtime_client, valid_pipeline_config)
        
        result = engine._invoke_endpoint("test-endpoint", "Test prompt")
        
        assert result == ""
