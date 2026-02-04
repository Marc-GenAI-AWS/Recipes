"""
Judge Component for Automated LLM Finetuning Pipeline

This module provides the Judge class that evaluates finetuned model responses
against baseline model responses using Claude Sonnet 4 as a judge.

Features:
- Batch evaluation of response pairs
- Structured judgment with winner, reasoning, and confidence
- Win rate calculation and metrics
- Retry logic with exponential backoff for transient errors
- Comprehensive error handling and logging
"""

import json
import time
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.config_models import (
    PipelineConfig,
    ResponsePair,
    ResponsePairs,
    Judgment,
    EvaluationResult
)
from src.logging_config import get_logger


# Module logger
logger = get_logger("judge")


class Judge:
    """
    Evaluates response quality using Claude Sonnet 4 as a judge.
    
    The Judge component:
    - Compares finetuned model responses against baseline responses
    - Uses Claude Sonnet 4 via AWS Bedrock for evaluation
    - Provides structured judgments with reasoning and confidence
    - Calculates win rates and performance metrics
    - Implements retry logic for transient errors
    
    Attributes:
        bedrock_client: AWS Bedrock Runtime client for Claude Sonnet 4
        config: Pipeline configuration with AWS settings and parameters
        model_id: Bedrock model ID for Claude Sonnet 4
    
    Example:
        >>> from src.aws_client_manager import AWSClientManager
        >>> from src.configuration_manager import ConfigurationManager
        >>> 
        >>> # Initialize components
        >>> config_manager = ConfigurationManager()
        >>> pipeline_config = config_manager.load_pipeline_config()
        >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
        >>> bedrock_client = aws_manager.get_bedrock_runtime_client()
        >>> 
        >>> # Create judge
        >>> judge = Judge(bedrock_client, pipeline_config)
        >>> 
        >>> # Evaluate response pairs
        >>> use_case = config_manager.load_use_case("customer_support")
        >>> evaluation = judge.evaluate(
        ...     response_pairs,
        ...     use_case.judge_prompt,
        ...     use_case.judge_criteria
        ... )
        >>> print(f"Win rate: {evaluation.win_rate:.1%}")
    """
    
    def __init__(
        self,
        bedrock_client: Any,
        config: PipelineConfig
    ):
        """
        Initialize Judge with Bedrock client and configuration.
        
        Sets up the judge with the necessary AWS Bedrock client for calling
        Claude Sonnet 4 and the pipeline configuration containing model settings,
        retry parameters, and other operational parameters.
        
        Args:
            bedrock_client: AWS Bedrock Runtime client instance for invoking
                          Claude Sonnet 4. Should be obtained from AWSClientManager.
                          Can be a real boto3 client or a mock for testing.
            config: PipelineConfig instance containing AWS region, Bedrock model ID,
                   retry settings, and other pipeline parameters.
        
        Raises:
            ValueError: If bedrock_client is None or config is None
            TypeError: If config is not a PipelineConfig instance
            AttributeError: If config is missing required attributes
        
        Example:
            >>> from src.aws_client_manager import AWSClientManager
            >>> from src.configuration_manager import ConfigurationManager
            >>> 
            >>> config_manager = ConfigurationManager()
            >>> pipeline_config = config_manager.load_pipeline_config()
            >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
            >>> bedrock_client = aws_manager.get_bedrock_runtime_client()
            >>> 
            >>> judge = Judge(bedrock_client, pipeline_config)
        """
        # Validate bedrock_client parameter
        if bedrock_client is None:
            raise ValueError("bedrock_client cannot be None")
        
        # Validate config parameter
        if config is None:
            raise ValueError("config cannot be None")
        
        # Validate config is a PipelineConfig instance
        if not isinstance(config, PipelineConfig):
            raise TypeError(
                f"config must be a PipelineConfig instance, got {type(config).__name__}"
            )
        
        # Validate config has required attributes
        required_attrs = [
            'bedrock_model_id',
            'aws_region',
            'max_retries',
            'initial_backoff_seconds',
            'max_backoff_seconds'
        ]
        
        missing_attrs = [attr for attr in required_attrs if not hasattr(config, attr)]
        if missing_attrs:
            raise AttributeError(
                f"config is missing required attributes: {', '.join(missing_attrs)}"
            )
        
        # Store client and configuration
        self.bedrock_client = bedrock_client
        self.config = config
        
        # Extract model ID for convenience
        self.model_id = config.bedrock_model_id
        
        logger.info(
            "Judge initialized",
            extra={
                "context": {
                    "model_id": self.model_id,
                    "region": self.config.aws_region,
                    "max_retries": self.config.max_retries,
                }
            }
        )
        
        logger.debug(
            "Judge configuration details",
            extra={
                "context": {
                    "bedrock_model_id": self.config.bedrock_model_id,
                    "initial_backoff_seconds": self.config.initial_backoff_seconds,
                    "max_backoff_seconds": self.config.max_backoff_seconds,
                }
            }
        )

    def evaluate(
        self,
        response_pairs: ResponsePairs,
        judge_prompt: str,
        judge_criteria: str
    ) -> EvaluationResult:
        """
        Evaluate all response pairs and calculate win rate.
        
        Compares each finetuned model response against the corresponding baseline
        response using Claude Sonnet 4 as a judge. Returns structured judgments
        with winner designation, reasoning, and confidence scores, along with
        aggregate metrics like win rate and tie rate.
        
        Args:
            response_pairs: ResponsePairs object containing questions and responses
                          from both finetuned and baseline models
            judge_prompt: Template prompt for the judge explaining evaluation approach
            judge_criteria: Specific criteria to use when evaluating responses
                          (e.g., helpfulness, accuracy, clarity)
        
        Returns:
            EvaluationResult containing:
                - judgments: List of Judgment objects for each response pair
                - win_rate: Percentage where finetuned model won (0.0 to 1.0)
                - tie_rate: Percentage of ties (0.0 to 1.0)
                - total_comparisons: Total number of response pairs evaluated
                - evaluation_time: Timestamp when evaluation completed
        
        Raises:
            ValueError: If response_pairs is empty or prompts are invalid
            RuntimeError: If evaluation fails after all retry attempts
        
        Example:
            >>> from src.inference_engine import InferenceEngine
            >>> 
            >>> # Generate responses
            >>> inference = InferenceEngine(sagemaker_runtime, config)
            >>> response_pairs = inference.generate_responses(
            ...     questions=use_case.test_questions,
            ...     finetuned_endpoint="my-finetuned-endpoint",
            ...     baseline_endpoint="baseline-endpoint"
            ... )
            >>> 
            >>> # Evaluate
            >>> judge = Judge(bedrock_client, config)
            >>> evaluation = judge.evaluate(
            ...     response_pairs,
            ...     use_case.judge_prompt,
            ...     use_case.judge_criteria
            ... )
            >>> 
            >>> print(f"Win rate: {evaluation.win_rate:.1%}")
            >>> print(f"Tie rate: {evaluation.tie_rate:.1%}")
            >>> for judgment in evaluation.judgments:
            ...     print(f"Q: {judgment.question}")
            ...     print(f"Winner: {judgment.winner}")
            ...     print(f"Reasoning: {judgment.reasoning}")
        """
        # Validate inputs
        if not response_pairs or not response_pairs.pairs:
            raise ValueError("response_pairs cannot be empty")
        
        if not judge_prompt or not judge_prompt.strip():
            raise ValueError("judge_prompt cannot be empty")
        
        if not judge_criteria or not judge_criteria.strip():
            raise ValueError("judge_criteria cannot be empty")
        
        logger.info(
            f"Starting evaluation of {len(response_pairs.pairs)} response pairs",
            extra={
                "context": {
                    "num_pairs": len(response_pairs.pairs),
                    "finetuned_endpoint": response_pairs.finetuned_endpoint,
                    "baseline_endpoint": response_pairs.baseline_endpoint,
                }
            }
        )
        
        # Evaluate each response pair
        judgments = []
        for i, pair in enumerate(response_pairs.pairs, 1):
            logger.info(
                f"Evaluating response pair {i}/{len(response_pairs.pairs)}",
                extra={
                    "context": {
                        "pair_index": i,
                        "total_pairs": len(response_pairs.pairs),
                        "question": pair.question[:100] + "..." if len(pair.question) > 100 else pair.question,
                    }
                }
            )
            
            # Judge single pair with retry logic
            judgment = self._judge_single_pair(
                pair,
                judge_prompt,
                judge_criteria
            )
            
            judgments.append(judgment)
            
            logger.debug(
                f"Judgment {i} complete",
                extra={
                    "context": {
                        "pair_index": i,
                        "winner": judgment.winner,
                        "confidence": judgment.confidence,
                    }
                }
            )
        
        # Calculate win rate
        win_rate = self._calculate_win_rate(judgments)
        
        # Calculate tie rate
        tie_count = sum(1 for j in judgments if j.winner == "tie")
        tie_rate = tie_count / len(judgments) if judgments else 0.0
        
        # Create evaluation result
        evaluation = EvaluationResult(
            judgments=judgments,
            win_rate=win_rate,
            tie_rate=tie_rate,
            total_comparisons=len(judgments),
            evaluation_time=datetime.now()
        )
        
        logger.info(
            "Evaluation complete",
            extra={
                "context": {
                    "total_comparisons": len(judgments),
                    "win_rate": win_rate,
                    "tie_rate": tie_rate,
                    "finetuned_wins": sum(1 for j in judgments if j.winner == "finetuned"),
                    "baseline_wins": sum(1 for j in judgments if j.winner == "baseline"),
                    "ties": tie_count,
                }
            }
        )
        
        return evaluation

    def _judge_single_pair(
        self,
        pair: ResponsePair,
        judge_prompt: str,
        judge_criteria: str
    ) -> Judgment:
        """
        Judge a single response pair using Claude Sonnet 4.
        
        Calls AWS Bedrock to invoke Claude Sonnet 4 with the judge prompt,
        criteria, question, and both responses. Implements exponential backoff
        retry logic for transient errors. Parses and validates the judgment.
        
        Args:
            pair: ResponsePair containing question and both responses
            judge_prompt: Template prompt for the judge
            judge_criteria: Evaluation criteria
        
        Returns:
            Judgment object with winner, reasoning, and confidence
        
        Raises:
            RuntimeError: If judgment fails after all retry attempts
            ValueError: If judgment response cannot be parsed
        """
        # Construct the full prompt for Claude
        full_prompt = f"""{judge_prompt}

Evaluation Criteria:
{judge_criteria}

Question:
{pair.question}

Response A (Finetuned Model):
{pair.finetuned_response}

Response B (Baseline Model):
{pair.baseline_response}

Please evaluate both responses based on the criteria above and provide your judgment in the following JSON format:
{{
    "winner": "A" or "B" or "tie",
    "reasoning": "Detailed explanation of your decision",
    "confidence": 0.0 to 1.0
}}

Return ONLY the JSON object, with no additional text or explanation."""
        
        # Retry with exponential backoff
        for attempt in range(self.config.max_retries):
            try:
                logger.debug(
                    f"Calling Bedrock API for judgment (attempt {attempt + 1}/{self.config.max_retries})",
                    extra={
                        "context": {
                            "model_id": self.model_id,
                            "attempt": attempt + 1,
                            "question": pair.question[:100] + "..." if len(pair.question) > 100 else pair.question,
                        }
                    }
                )
                
                # Prepare request body for Claude
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2048,
                    "messages": [
                        {
                            "role": "user",
                            "content": full_prompt
                        }
                    ],
                    "temperature": 0.3,  # Lower temperature for more consistent judgments
                }
                
                # Invoke Bedrock
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                content = response_body['content'][0]['text']
                
                # Parse judgment from response
                judgment = self._parse_judgment(content, pair.question)
                
                logger.info(
                    "Successfully generated judgment",
                    extra={
                        "context": {
                            "winner": judgment.winner,
                            "confidence": judgment.confidence,
                        }
                    }
                )
                
                return judgment
                
            except Exception as e:
                logger.warning(
                    f"Judgment attempt {attempt + 1} failed: {e}",
                    extra={
                        "context": {
                            "attempt": attempt + 1,
                            "max_retries": self.config.max_retries,
                            "error": str(e),
                            "question": pair.question[:100] + "..." if len(pair.question) > 100 else pair.question,
                        }
                    }
                )
                
                # If this was the last attempt, raise the error
                if attempt == self.config.max_retries - 1:
                    logger.error(
                        "Judgment failed after all retry attempts",
                        extra={
                            "context": {
                                "max_retries": self.config.max_retries,
                                "final_error": str(e),
                                "question": pair.question,
                            }
                        }
                    )
                    raise RuntimeError(
                        f"Failed to generate judgment after {self.config.max_retries} attempts: {e}"
                    )
                
                # Calculate backoff delay with exponential backoff
                backoff = min(
                    self.config.initial_backoff_seconds * (2 ** attempt),
                    self.config.max_backoff_seconds
                )
                
                logger.info(
                    f"Retrying in {backoff} seconds...",
                    extra={"context": {"backoff_seconds": backoff}}
                )
                
                time.sleep(backoff)
        
        # This should never be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in judgment generation")

    def _parse_judgment(self, content: str, question: str) -> Judgment:
        """
        Parse judgment from Claude's response.
        
        Extracts and validates the JSON judgment from Claude's response,
        handling various response formats and edge cases.
        
        Args:
            content: Raw response content from Claude
            question: Original question being judged
        
        Returns:
            Judgment object with validated fields
        
        Raises:
            ValueError: If response cannot be parsed or is invalid
        """
        try:
            # Extract JSON from response
            # Claude might wrap the JSON in markdown code blocks
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            if content.startswith('```'):
                content = content[3:]  # Remove ```
            if content.endswith('```'):
                content = content[:-3]  # Remove trailing ```
            content = content.strip()
            
            # Parse JSON
            judgment_data = json.loads(content)
            
            # Validate required fields
            if 'winner' not in judgment_data:
                raise ValueError("Judgment missing 'winner' field")
            if 'reasoning' not in judgment_data:
                raise ValueError("Judgment missing 'reasoning' field")
            
            # Extract and validate winner
            winner_raw = judgment_data['winner'].strip().upper()
            if winner_raw == 'A':
                winner = 'finetuned'
            elif winner_raw == 'B':
                winner = 'baseline'
            elif winner_raw == 'TIE':
                winner = 'tie'
            else:
                # Try to parse from full words
                winner_lower = judgment_data['winner'].strip().lower()
                if 'finetuned' in winner_lower or winner_lower == 'a':
                    winner = 'finetuned'
                elif 'baseline' in winner_lower or winner_lower == 'b':
                    winner = 'baseline'
                elif 'tie' in winner_lower:
                    winner = 'tie'
                else:
                    logger.warning(
                        f"Invalid winner value: {judgment_data['winner']}, defaulting to 'tie'",
                        extra={"context": {"winner_value": judgment_data['winner']}}
                    )
                    winner = 'tie'
            
            # Extract reasoning
            reasoning = judgment_data['reasoning'].strip()
            if not reasoning:
                raise ValueError("Judgment reasoning cannot be empty")
            
            # Extract confidence (default to 0.8 if not provided)
            confidence = float(judgment_data.get('confidence', 0.8))
            
            # Validate confidence is in valid range
            if not 0.0 <= confidence <= 1.0:
                logger.warning(
                    f"Confidence {confidence} out of range [0, 1], clamping",
                    extra={"context": {"confidence": confidence}}
                )
                confidence = max(0.0, min(1.0, confidence))
            
            # Create judgment object
            judgment = Judgment(
                question=question,
                winner=winner,
                reasoning=reasoning,
                confidence=confidence
            )
            
            logger.debug(
                "Successfully parsed judgment",
                extra={
                    "context": {
                        "winner": winner,
                        "confidence": confidence,
                        "reasoning_length": len(reasoning),
                    }
                }
            )
            
            return judgment
            
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse judgment JSON: {e}",
                extra={
                    "context": {
                        "error": str(e),
                        "content": content[:500] + "..." if len(content) > 500 else content,
                    }
                }
            )
            raise ValueError(f"Failed to parse judgment JSON: {e}")
        
        except Exception as e:
            logger.error(
                f"Failed to parse judgment: {e}",
                extra={
                    "context": {
                        "error": str(e),
                        "content": content[:500] + "..." if len(content) > 500 else content,
                    }
                }
            )
            raise ValueError(f"Failed to parse judgment: {e}")

    def _calculate_win_rate(self, judgments: List[Judgment]) -> float:
        """
        Calculate win rate as percentage where finetuned model won.
        
        Computes the win rate by counting the number of judgments where the
        finetuned model was judged superior and dividing by the total number
        of judgments. Ties are not counted as wins.
        
        Args:
            judgments: List of Judgment objects from evaluation
        
        Returns:
            Win rate as a float between 0.0 and 1.0
        
        Example:
            >>> judgments = [
            ...     Judgment(question="Q1", winner="finetuned", reasoning="...", confidence=0.9),
            ...     Judgment(question="Q2", winner="baseline", reasoning="...", confidence=0.8),
            ...     Judgment(question="Q3", winner="finetuned", reasoning="...", confidence=0.85),
            ...     Judgment(question="Q4", winner="tie", reasoning="...", confidence=0.7),
            ... ]
            >>> judge = Judge(bedrock_client, config)
            >>> win_rate = judge._calculate_win_rate(judgments)
            >>> print(f"Win rate: {win_rate:.1%}")  # 50.0% (2 wins out of 4 total)
        """
        if not judgments:
            logger.warning("No judgments provided for win rate calculation")
            return 0.0
        
        # Count wins for finetuned model
        finetuned_wins = sum(1 for j in judgments if j.winner == "finetuned")
        
        # Calculate win rate
        win_rate = finetuned_wins / len(judgments)
        
        logger.debug(
            "Win rate calculated",
            extra={
                "context": {
                    "finetuned_wins": finetuned_wins,
                    "total_judgments": len(judgments),
                    "win_rate": win_rate,
                }
            }
        )
        
        return win_rate
