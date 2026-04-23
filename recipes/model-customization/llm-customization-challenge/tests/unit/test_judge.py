"""
Unit tests for Judge component

Tests the Judge class that evaluates finetuned model responses against
baseline responses using Claude Sonnet 4 as a judge.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from io import BytesIO

from src.judge import Judge
from src.config_models import (
    PipelineConfig,
    ResponsePair,
    ResponsePairs,
    Judgment,
    EvaluationResult
)


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock Runtime client"""
    client = Mock()
    return client


@pytest.fixture
def pipeline_config():
    """Create a test pipeline configuration"""
    return PipelineConfig(
        aws_region="us-east-1",
        bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        sagemaker_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
        training_instance_type="ml.g5.2xlarge",
        inference_instance_type="ml.g5.xlarge",
        baseline_model_endpoint="baseline-endpoint",
        performance_threshold=0.60,
        max_iterations=5,
        cleanup_resources=True,
        s3_bucket="test-bucket",
        max_retries=3,
        initial_backoff_seconds=2,
        max_backoff_seconds=60
    )


@pytest.fixture
def sample_response_pairs():
    """Create sample response pairs for testing"""
    pairs = [
        ResponsePair(
            question="What is the capital of France?",
            finetuned_response="The capital of France is Paris.",
            baseline_response="Paris is the capital city of France."
        ),
        ResponsePair(
            question="How do I reset my password?",
            finetuned_response="To reset your password, click 'Forgot Password' on the login page.",
            baseline_response="You can reset your password by clicking the forgot password link."
        ),
        ResponsePair(
            question="What are the benefits of exercise?",
            finetuned_response="Exercise improves cardiovascular health, strengthens muscles, and boosts mood.",
            baseline_response="Regular exercise has many health benefits including better heart health."
        )
    ]
    
    return ResponsePairs(
        pairs=pairs,
        finetuned_endpoint="finetuned-endpoint",
        baseline_endpoint="baseline-endpoint",
        generation_time=datetime.now()
    )


class TestJudgeInit:
    """Tests for Judge.__init__()"""
    
    def test_init_success(self, mock_bedrock_client, pipeline_config):
        """Test successful initialization"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        assert judge.bedrock_client == mock_bedrock_client
        assert judge.config == pipeline_config
        assert judge.model_id == pipeline_config.bedrock_model_id
    
    def test_init_none_bedrock_client(self, pipeline_config):
        """Test initialization with None bedrock_client raises ValueError"""
        with pytest.raises(ValueError, match="bedrock_client cannot be None"):
            Judge(None, pipeline_config)
    
    def test_init_none_config(self, mock_bedrock_client):
        """Test initialization with None config raises ValueError"""
        with pytest.raises(ValueError, match="config cannot be None"):
            Judge(mock_bedrock_client, None)
    
    def test_init_invalid_config_type(self, mock_bedrock_client):
        """Test initialization with invalid config type raises TypeError"""
        with pytest.raises(TypeError, match="config must be a PipelineConfig instance"):
            Judge(mock_bedrock_client, {"invalid": "config"})
    
    def test_init_missing_required_attributes(self, mock_bedrock_client):
        """Test initialization with config missing required attributes"""
        # Create a PipelineConfig-like object without required attributes
        # We need to bypass the isinstance check by creating an actual PipelineConfig
        # but then removing attributes
        config = PipelineConfig(
            aws_region="us-east-1",
            bedrock_model_id="test-model",
            sagemaker_role_arn="arn:aws:iam::123456789012:role/Test",
            training_instance_type="ml.g5.2xlarge",
            inference_instance_type="ml.g5.xlarge",
            baseline_model_endpoint="baseline",
            performance_threshold=0.6,
            max_iterations=5,
            cleanup_resources=True,
            s3_bucket="test-bucket",
            max_retries=3,
            initial_backoff_seconds=2,
            max_backoff_seconds=60
        )
        
        # Remove a required attribute
        delattr(config, 'bedrock_model_id')
        
        with pytest.raises(AttributeError, match="config is missing required attributes"):
            Judge(mock_bedrock_client, config)


class TestJudgeEvaluate:
    """Tests for Judge.evaluate()"""
    
    def test_evaluate_success(self, mock_bedrock_client, pipeline_config, sample_response_pairs):
        """Test successful evaluation of response pairs"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        # Mock Bedrock responses
        mock_responses = [
            {
                "winner": "A",
                "reasoning": "Response A is more concise and direct.",
                "confidence": 0.9
            },
            {
                "winner": "B",
                "reasoning": "Response B provides more context.",
                "confidence": 0.8
            },
            {
                "winner": "A",
                "reasoning": "Response A is more comprehensive.",
                "confidence": 0.85
            }
        ]
        
        def mock_invoke_model(**kwargs):
            # Get the current call index
            call_count = mock_bedrock_client.invoke_model.call_count
            response_data = mock_responses[call_count - 1]
            
            response_body = {
                'content': [{'text': json.dumps(response_data)}]
            }
            
            return {
                'body': BytesIO(json.dumps(response_body).encode('utf-8'))
            }
        
        mock_bedrock_client.invoke_model = Mock(side_effect=mock_invoke_model)
        
        # Evaluate
        result = judge.evaluate(
            sample_response_pairs,
            judge_prompt="Compare the responses",
            judge_criteria="Evaluate based on clarity and completeness"
        )
        
        # Verify result
        assert isinstance(result, EvaluationResult)
        assert len(result.judgments) == 3
        assert result.total_comparisons == 3
        assert result.win_rate == 2/3  # 2 wins for finetuned (A)
        assert result.tie_rate == 0.0
        assert isinstance(result.evaluation_time, datetime)
        
        # Verify judgments
        assert result.judgments[0].winner == "finetuned"
        assert result.judgments[1].winner == "baseline"
        assert result.judgments[2].winner == "finetuned"
        
        # Verify Bedrock was called correctly
        assert mock_bedrock_client.invoke_model.call_count == 3
    
    def test_evaluate_empty_response_pairs(self, mock_bedrock_client, pipeline_config):
        """Test evaluation with empty response pairs raises ValueError"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        empty_pairs = ResponsePairs(
            pairs=[],
            finetuned_endpoint="finetuned-endpoint",
            baseline_endpoint="baseline-endpoint",
            generation_time=datetime.now()
        )
        
        with pytest.raises(ValueError, match="response_pairs cannot be empty"):
            judge.evaluate(
                empty_pairs,
                judge_prompt="Compare the responses",
                judge_criteria="Evaluate based on clarity"
            )
    
    def test_evaluate_empty_judge_prompt(self, mock_bedrock_client, pipeline_config, sample_response_pairs):
        """Test evaluation with empty judge_prompt raises ValueError"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        with pytest.raises(ValueError, match="judge_prompt cannot be empty"):
            judge.evaluate(
                sample_response_pairs,
                judge_prompt="",
                judge_criteria="Evaluate based on clarity"
            )
    
    def test_evaluate_empty_judge_criteria(self, mock_bedrock_client, pipeline_config, sample_response_pairs):
        """Test evaluation with empty judge_criteria raises ValueError"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        with pytest.raises(ValueError, match="judge_criteria cannot be empty"):
            judge.evaluate(
                sample_response_pairs,
                judge_prompt="Compare the responses",
                judge_criteria=""
            )
    
    def test_evaluate_with_ties(self, mock_bedrock_client, pipeline_config, sample_response_pairs):
        """Test evaluation with tie results"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        # Mock Bedrock responses with ties
        mock_responses = [
            {"winner": "A", "reasoning": "Response A is better.", "confidence": 0.9},
            {"winner": "tie", "reasoning": "Both responses are equally good.", "confidence": 0.7},
            {"winner": "B", "reasoning": "Response B is better.", "confidence": 0.85}
        ]
        
        def mock_invoke_model(**kwargs):
            call_count = mock_bedrock_client.invoke_model.call_count
            response_data = mock_responses[call_count - 1]
            response_body = {'content': [{'text': json.dumps(response_data)}]}
            return {'body': BytesIO(json.dumps(response_body).encode('utf-8'))}
        
        mock_bedrock_client.invoke_model = Mock(side_effect=mock_invoke_model)
        
        # Evaluate
        result = judge.evaluate(
            sample_response_pairs,
            judge_prompt="Compare the responses",
            judge_criteria="Evaluate based on clarity"
        )
        
        # Verify tie handling
        assert result.win_rate == 1/3  # 1 win for finetuned
        assert result.tie_rate == 1/3  # 1 tie
        assert result.judgments[1].winner == "tie"


class TestJudgeSinglePair:
    """Tests for Judge._judge_single_pair()"""
    
    def test_judge_single_pair_success(self, mock_bedrock_client, pipeline_config):
        """Test successful judgment of a single pair"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        pair = ResponsePair(
            question="What is AI?",
            finetuned_response="AI is artificial intelligence.",
            baseline_response="Artificial intelligence is AI."
        )
        
        # Mock Bedrock response
        judgment_data = {
            "winner": "A",
            "reasoning": "Response A is more natural.",
            "confidence": 0.9
        }
        
        response_body = {
            'content': [{'text': json.dumps(judgment_data)}]
        }
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(response_body).encode('utf-8'))
        }
        
        # Judge pair
        judgment = judge._judge_single_pair(
            pair,
            judge_prompt="Compare the responses",
            judge_criteria="Evaluate based on naturalness"
        )
        
        # Verify judgment
        assert isinstance(judgment, Judgment)
        assert judgment.question == pair.question
        assert judgment.winner == "finetuned"
        assert judgment.reasoning == "Response A is more natural."
        assert judgment.confidence == 0.9
    
    def test_judge_single_pair_with_retry(self, mock_bedrock_client, pipeline_config):
        """Test judgment with retry on transient error"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        pair = ResponsePair(
            question="What is AI?",
            finetuned_response="AI is artificial intelligence.",
            baseline_response="Artificial intelligence is AI."
        )
        
        # Mock first call to fail, second to succeed
        judgment_data = {
            "winner": "B",
            "reasoning": "Response B is clearer.",
            "confidence": 0.85
        }
        
        response_body = {
            'content': [{'text': json.dumps(judgment_data)}]
        }
        
        mock_bedrock_client.invoke_model.side_effect = [
            Exception("Throttling error"),
            {'body': BytesIO(json.dumps(response_body).encode('utf-8'))}
        ]
        
        # Judge pair (should succeed on retry)
        with patch('time.sleep'):  # Mock sleep to speed up test
            judgment = judge._judge_single_pair(
                pair,
                judge_prompt="Compare the responses",
                judge_criteria="Evaluate based on clarity"
            )
        
        # Verify judgment
        assert judgment.winner == "baseline"
        assert mock_bedrock_client.invoke_model.call_count == 2
    
    def test_judge_single_pair_max_retries_exceeded(self, mock_bedrock_client, pipeline_config):
        """Test judgment fails after max retries"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        pair = ResponsePair(
            question="What is AI?",
            finetuned_response="AI is artificial intelligence.",
            baseline_response="Artificial intelligence is AI."
        )
        
        # Mock all calls to fail
        mock_bedrock_client.invoke_model.side_effect = Exception("Persistent error")
        
        # Judge pair should raise RuntimeError
        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(RuntimeError, match="Failed to generate judgment after"):
                judge._judge_single_pair(
                    pair,
                    judge_prompt="Compare the responses",
                    judge_criteria="Evaluate based on clarity"
                )
        
        # Verify max retries were attempted
        assert mock_bedrock_client.invoke_model.call_count == pipeline_config.max_retries


class TestParseJudgment:
    """Tests for Judge._parse_judgment()"""
    
    def test_parse_judgment_valid_json(self, mock_bedrock_client, pipeline_config):
        """Test parsing valid JSON judgment"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "winner": "A",
            "reasoning": "Response A is better because it's more concise.",
            "confidence": 0.9
        })
        
        judgment = judge._parse_judgment(content, "What is AI?")
        
        assert judgment.question == "What is AI?"
        assert judgment.winner == "finetuned"
        assert judgment.reasoning == "Response A is better because it's more concise."
        assert judgment.confidence == 0.9
    
    def test_parse_judgment_with_markdown(self, mock_bedrock_client, pipeline_config):
        """Test parsing judgment wrapped in markdown code blocks"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = """```json
{
    "winner": "B",
    "reasoning": "Response B provides more detail.",
    "confidence": 0.85
}
```"""
        
        judgment = judge._parse_judgment(content, "How does it work?")
        
        assert judgment.winner == "baseline"
        assert judgment.reasoning == "Response B provides more detail."
        assert judgment.confidence == 0.85
    
    def test_parse_judgment_tie(self, mock_bedrock_client, pipeline_config):
        """Test parsing tie judgment"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "winner": "tie",
            "reasoning": "Both responses are equally good.",
            "confidence": 0.7
        })
        
        judgment = judge._parse_judgment(content, "What is the answer?")
        
        assert judgment.winner == "tie"
    
    def test_parse_judgment_missing_confidence(self, mock_bedrock_client, pipeline_config):
        """Test parsing judgment without confidence (should default to 0.8)"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "winner": "A",
            "reasoning": "Response A is better."
        })
        
        judgment = judge._parse_judgment(content, "Question?")
        
        assert judgment.confidence == 0.8
    
    def test_parse_judgment_confidence_out_of_range(self, mock_bedrock_client, pipeline_config):
        """Test parsing judgment with confidence out of range (should clamp)"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "winner": "A",
            "reasoning": "Response A is better.",
            "confidence": 1.5
        })
        
        judgment = judge._parse_judgment(content, "Question?")
        
        assert judgment.confidence == 1.0  # Clamped to max
    
    def test_parse_judgment_invalid_json(self, mock_bedrock_client, pipeline_config):
        """Test parsing invalid JSON raises ValueError"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = "This is not valid JSON"
        
        with pytest.raises(ValueError, match="Failed to parse judgment JSON"):
            judge._parse_judgment(content, "Question?")
    
    def test_parse_judgment_missing_winner(self, mock_bedrock_client, pipeline_config):
        """Test parsing judgment missing winner field raises ValueError"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "reasoning": "Some reasoning.",
            "confidence": 0.8
        })
        
        with pytest.raises(ValueError, match="Judgment missing 'winner' field"):
            judge._parse_judgment(content, "Question?")
    
    def test_parse_judgment_missing_reasoning(self, mock_bedrock_client, pipeline_config):
        """Test parsing judgment missing reasoning field raises ValueError"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "winner": "A",
            "confidence": 0.8
        })
        
        with pytest.raises(ValueError, match="Judgment missing 'reasoning' field"):
            judge._parse_judgment(content, "Question?")
    
    def test_parse_judgment_empty_reasoning(self, mock_bedrock_client, pipeline_config):
        """Test parsing judgment with empty reasoning raises ValueError"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "winner": "A",
            "reasoning": "",
            "confidence": 0.8
        })
        
        with pytest.raises(ValueError, match="Judgment reasoning cannot be empty"):
            judge._parse_judgment(content, "Question?")
    
    def test_parse_judgment_invalid_winner_defaults_to_tie(self, mock_bedrock_client, pipeline_config):
        """Test parsing judgment with invalid winner defaults to tie"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        content = json.dumps({
            "winner": "invalid_value",
            "reasoning": "Some reasoning.",
            "confidence": 0.8
        })
        
        judgment = judge._parse_judgment(content, "Question?")
        
        assert judgment.winner == "tie"


class TestCalculateWinRate:
    """Tests for Judge._calculate_win_rate()"""
    
    def test_calculate_win_rate_all_wins(self, mock_bedrock_client, pipeline_config):
        """Test win rate calculation when finetuned wins all"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        judgments = [
            Judgment(question="Q1", winner="finetuned", reasoning="...", confidence=0.9),
            Judgment(question="Q2", winner="finetuned", reasoning="...", confidence=0.8),
            Judgment(question="Q3", winner="finetuned", reasoning="...", confidence=0.85)
        ]
        
        win_rate = judge._calculate_win_rate(judgments)
        
        assert win_rate == 1.0
    
    def test_calculate_win_rate_no_wins(self, mock_bedrock_client, pipeline_config):
        """Test win rate calculation when finetuned wins none"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        judgments = [
            Judgment(question="Q1", winner="baseline", reasoning="...", confidence=0.9),
            Judgment(question="Q2", winner="baseline", reasoning="...", confidence=0.8),
            Judgment(question="Q3", winner="baseline", reasoning="...", confidence=0.85)
        ]
        
        win_rate = judge._calculate_win_rate(judgments)
        
        assert win_rate == 0.0
    
    def test_calculate_win_rate_mixed(self, mock_bedrock_client, pipeline_config):
        """Test win rate calculation with mixed results"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        judgments = [
            Judgment(question="Q1", winner="finetuned", reasoning="...", confidence=0.9),
            Judgment(question="Q2", winner="baseline", reasoning="...", confidence=0.8),
            Judgment(question="Q3", winner="finetuned", reasoning="...", confidence=0.85),
            Judgment(question="Q4", winner="baseline", reasoning="...", confidence=0.7)
        ]
        
        win_rate = judge._calculate_win_rate(judgments)
        
        assert win_rate == 0.5
    
    def test_calculate_win_rate_with_ties(self, mock_bedrock_client, pipeline_config):
        """Test win rate calculation with ties (ties don't count as wins)"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        judgments = [
            Judgment(question="Q1", winner="finetuned", reasoning="...", confidence=0.9),
            Judgment(question="Q2", winner="tie", reasoning="...", confidence=0.7),
            Judgment(question="Q3", winner="finetuned", reasoning="...", confidence=0.85),
            Judgment(question="Q4", winner="tie", reasoning="...", confidence=0.6)
        ]
        
        win_rate = judge._calculate_win_rate(judgments)
        
        assert win_rate == 0.5  # 2 wins out of 4 total
    
    def test_calculate_win_rate_empty_list(self, mock_bedrock_client, pipeline_config):
        """Test win rate calculation with empty judgment list"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        win_rate = judge._calculate_win_rate([])
        
        assert win_rate == 0.0
    
    def test_calculate_win_rate_single_judgment(self, mock_bedrock_client, pipeline_config):
        """Test win rate calculation with single judgment"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        judgments = [
            Judgment(question="Q1", winner="finetuned", reasoning="...", confidence=0.9)
        ]
        
        win_rate = judge._calculate_win_rate(judgments)
        
        assert win_rate == 1.0


class TestJudgeIntegration:
    """Integration tests for Judge component"""
    
    def test_end_to_end_evaluation(self, mock_bedrock_client, pipeline_config):
        """Test complete evaluation workflow"""
        judge = Judge(mock_bedrock_client, pipeline_config)
        
        # Create response pairs
        pairs = [
            ResponsePair(
                question="What is machine learning?",
                finetuned_response="Machine learning is a subset of AI that enables systems to learn from data.",
                baseline_response="ML is when computers learn from data without being explicitly programmed."
            ),
            ResponsePair(
                question="How do neural networks work?",
                finetuned_response="Neural networks process information through layers of interconnected nodes.",
                baseline_response="They work by passing data through layers of neurons that learn patterns."
            )
        ]
        
        response_pairs = ResponsePairs(
            pairs=pairs,
            finetuned_endpoint="finetuned-endpoint",
            baseline_endpoint="baseline-endpoint",
            generation_time=datetime.now()
        )
        
        # Mock Bedrock responses
        mock_responses = [
            {"winner": "A", "reasoning": "More comprehensive.", "confidence": 0.9},
            {"winner": "B", "reasoning": "More accessible.", "confidence": 0.8}
        ]
        
        def mock_invoke_model(**kwargs):
            call_count = mock_bedrock_client.invoke_model.call_count
            response_data = mock_responses[call_count - 1]
            response_body = {'content': [{'text': json.dumps(response_data)}]}
            return {'body': BytesIO(json.dumps(response_body).encode('utf-8'))}
        
        mock_bedrock_client.invoke_model = Mock(side_effect=mock_invoke_model)
        
        # Evaluate
        result = judge.evaluate(
            response_pairs,
            judge_prompt="Compare these responses on technical accuracy and clarity.",
            judge_criteria="Evaluate based on comprehensiveness and accessibility."
        )
        
        # Verify complete result
        assert len(result.judgments) == 2
        assert result.total_comparisons == 2
        assert result.win_rate == 0.5
        assert result.tie_rate == 0.0
        assert all(isinstance(j, Judgment) for j in result.judgments)
        assert all(j.confidence > 0 for j in result.judgments)
        assert all(j.reasoning for j in result.judgments)
