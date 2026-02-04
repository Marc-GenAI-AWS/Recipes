"""
Inference Engine for Automated LLM Finetuning Pipeline

This module provides the InferenceEngine class that generates responses from both
finetuned and baseline models using AWS SageMaker endpoints.

Features:
- Batch inference for multiple questions
- Retry logic with exponential backoff for transient errors
- Model-specific prompt formatting
- Response cleaning and normalization
- Comprehensive error handling and logging
"""

import time
import re
import unicodedata
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.config_models import PipelineConfig, ResponsePair, ResponsePairs
from src.logging_config import get_logger, log_with_context


# Module logger
logger = get_logger("inference_engine")


class InferenceEngine:
    """
    Generates responses from both finetuned and baseline models.
    
    The InferenceEngine handles:
    - Batch inference for multiple test questions
    - Retry logic with exponential backoff for transient errors
    - Model-specific prompt formatting
    - Response cleaning and normalization
    - Progress tracking during inference
    """
    
    def __init__(self, sagemaker_runtime_client, config: PipelineConfig):
        """
        Initialize InferenceEngine with SageMaker runtime client.
        
        Args:
            sagemaker_runtime_client: Boto3 SageMaker Runtime client for endpoint invocation
            config: Pipeline configuration with inference settings
            
        Raises:
            ValueError: If sagemaker_runtime_client or config is None
        """
        if sagemaker_runtime_client is None:
            raise ValueError("sagemaker_runtime_client cannot be None")
        if config is None:
            raise ValueError("config cannot be None")
        
        self.sagemaker_runtime_client = sagemaker_runtime_client
        self.config = config
        
        logger.info(
            "InferenceEngine initialized",
            extra={
                "inference_instance_type": config.inference_instance_type,
                "baseline_endpoint": config.baseline_model_endpoint,
                "max_retries": config.max_retries
            }
        )
    
    def generate_responses(
        self,
        questions: List[str],
        finetuned_endpoint: str,
        baseline_endpoint: Optional[str] = None
    ) -> ResponsePairs:
        """
        Generate responses from both finetuned and baseline models for all questions.
        
        Args:
            questions: List of test questions to generate responses for
            finetuned_endpoint: Name of the finetuned model endpoint
            baseline_endpoint: Name of the baseline model endpoint (uses config default if None)
            
        Returns:
            ResponsePairs object containing all response pairs with metadata
            
        Raises:
            ValueError: If questions list is empty or endpoints are invalid
            RuntimeError: If inference fails after all retries
        """
        if not questions:
            raise ValueError("questions list cannot be empty")
        if not finetuned_endpoint or not finetuned_endpoint.strip():
            raise ValueError("finetuned_endpoint cannot be empty")
        
        # Use baseline endpoint from config if not provided
        if baseline_endpoint is None:
            baseline_endpoint = self.config.baseline_model_endpoint
        
        if not baseline_endpoint or not baseline_endpoint.strip():
            raise ValueError("baseline_endpoint cannot be empty")
        
        logger.info(
            f"Starting response generation for {len(questions)} questions",
            extra={
                "num_questions": len(questions),
                "finetuned_endpoint": finetuned_endpoint,
                "baseline_endpoint": baseline_endpoint
            }
        )
        
        pairs = []
        
        for i, question in enumerate(questions, 1):
            logger.info(
                f"Generating responses for question {i}/{len(questions)}",
                extra={"question_index": i, "total_questions": len(questions)}
            )
            
            # Format prompt for the question
            prompt = self._format_prompt(question)
            
            # Generate response from finetuned model
            finetuned_response = self._invoke_endpoint(
                finetuned_endpoint,
                prompt,
                max_retries=self.config.max_retries
            )
            
            # Generate response from baseline model
            baseline_response = self._invoke_endpoint(
                baseline_endpoint,
                prompt,
                max_retries=self.config.max_retries
            )
            
            # Clean and normalize responses
            finetuned_response = self._clean_response(finetuned_response)
            baseline_response = self._clean_response(baseline_response)
            
            # Create response pair
            pair = ResponsePair(
                question=question,
                finetuned_response=finetuned_response,
                baseline_response=baseline_response
            )
            pairs.append(pair)
            
            logger.debug(
                f"Generated response pair {i}/{len(questions)}",
                extra={
                    "question_index": i,
                    "finetuned_length": len(finetuned_response),
                    "baseline_length": len(baseline_response)
                }
            )
        
        response_pairs = ResponsePairs(
            pairs=pairs,
            finetuned_endpoint=finetuned_endpoint,
            baseline_endpoint=baseline_endpoint,
            generation_time=datetime.now()
        )
        
        logger.info(
            f"Response generation complete: {len(pairs)} pairs generated",
            extra={"num_pairs": len(pairs)}
        )
        
        return response_pairs
    
    def _invoke_endpoint(
        self,
        endpoint_name: str,
        prompt: str,
        max_retries: int = 3
    ) -> str:
        """
        Invoke SageMaker endpoint with retry logic.
        
        Implements exponential backoff retry pattern for transient errors.
        
        Args:
            endpoint_name: Name of the SageMaker endpoint to invoke
            prompt: Formatted prompt to send to the model
            max_retries: Maximum number of retry attempts
            
        Returns:
            Model response as a string
            
        Raises:
            RuntimeError: If all retry attempts fail
        """
        import json
        
        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"Invoking endpoint (attempt {attempt + 1}/{max_retries})",
                    extra={
                        "endpoint_name": endpoint_name,
                        "attempt": attempt + 1,
                        "max_retries": max_retries
                    }
                )
                
                # Prepare request payload
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": 512,
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "do_sample": True
                    }
                }
                
                # Invoke endpoint
                response = self.sagemaker_runtime_client.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType="application/json",
                    Body=json.dumps(payload)
                )
                
                # Parse response
                response_body = json.loads(response['Body'].read().decode('utf-8'))
                
                # Extract generated text from response
                # Handle different response formats
                if isinstance(response_body, list) and len(response_body) > 0:
                    generated_text = response_body[0].get('generated_text', '')
                elif isinstance(response_body, dict):
                    generated_text = response_body.get('generated_text', '')
                    if not generated_text:
                        generated_text = response_body.get('outputs', '')
                else:
                    generated_text = str(response_body)
                
                logger.debug(
                    f"Endpoint invocation successful",
                    extra={
                        "endpoint_name": endpoint_name,
                        "response_length": len(generated_text)
                    }
                )
                
                return generated_text
                
            except Exception as e:
                error_msg = str(e)
                is_transient = self._is_transient_error(e)
                
                logger.warning(
                    f"Endpoint invocation failed (attempt {attempt + 1}/{max_retries})",
                    extra={
                        "endpoint_name": endpoint_name,
                        "attempt": attempt + 1,
                        "error": error_msg,
                        "is_transient": is_transient
                    }
                )
                
                # If this is the last attempt or error is not transient, raise
                if attempt == max_retries - 1 or not is_transient:
                    logger.error(
                        f"Endpoint invocation failed after {attempt + 1} attempts",
                        extra={
                            "endpoint_name": endpoint_name,
                            "total_attempts": attempt + 1,
                            "error": error_msg
                        }
                    )
                    raise RuntimeError(
                        f"Failed to invoke endpoint {endpoint_name} after {attempt + 1} attempts: {error_msg}"
                    ) from e
                
                # Calculate exponential backoff delay
                backoff = self._calculate_backoff(attempt)
                logger.info(
                    f"Retrying after {backoff:.2f}s backoff",
                    extra={"backoff_seconds": backoff, "attempt": attempt + 1}
                )
                time.sleep(backoff)
        
        # Should never reach here, but just in case
        raise RuntimeError(f"Failed to invoke endpoint {endpoint_name} after {max_retries} attempts")
    
    def _format_prompt(self, question: str) -> str:
        """
        Format question into model-specific prompt.
        
        Formats the question according to the model's expected input format.
        For Llama models, uses the instruction format.
        
        Args:
            question: Raw question text
            
        Returns:
            Formatted prompt string
        """
        # Llama 3.2 instruction format
        # Using a simple instruction format that works well with finetuned models
        formatted_prompt = f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>

{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        
        return formatted_prompt
    
    def _clean_response(self, response: str) -> str:
        """
        Clean and normalize model response.
        
        Performs:
        - Unicode normalization
        - Whitespace normalization
        - Removal of special tokens
        - Trimming
        
        Args:
            response: Raw model response
            
        Returns:
            Cleaned and normalized response
        """
        if not response:
            return ""
        
        # Normalize unicode characters
        response = unicodedata.normalize('NFKC', response)
        
        # Remove common special tokens and their content
        # Remove header patterns like <|start_header_id|>assistant<|end_header_id|>
        response = re.sub(r'<\|start_header_id\|>[^<]*<\|end_header_id\|>', '', response)
        
        # Remove other special tokens
        special_tokens = [
            '<|begin_of_text|>',
            '<|end_of_text|>',
            '<|eot_id|>',
            '<|assistant|>',
            '<|user|>',
            '<|system|>',
        ]
        
        for token in special_tokens:
            response = response.replace(token, '')
        
        # Normalize whitespace
        # Replace multiple spaces with single space
        response = re.sub(r' +', ' ', response)
        
        # Replace multiple newlines with double newline
        response = re.sub(r'\n\n+', '\n\n', response)
        
        # Remove leading/trailing whitespace
        response = response.strip()
        
        return response
    
    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and should be retried.
        
        Args:
            error: Exception that occurred
            
        Returns:
            True if error is transient, False otherwise
        """
        # Check for common transient error patterns
        error_str = str(error).lower()
        
        transient_patterns = [
            'throttling',
            'rate exceeded',
            'timeout',
            'timed out',
            'connection',
            'service unavailable',
            'internal server error',
            'temporarily unavailable',
            '429',  # Too Many Requests
            '500',  # Internal Server Error
            '502',  # Bad Gateway
            '503',  # Service Unavailable
            '504',  # Gateway Timeout
        ]
        
        for pattern in transient_patterns:
            if pattern in error_str:
                return True
        
        # Check exception type
        transient_types = [
            'ConnectionError',
            'Timeout',
            'ThrottlingException',
            'ServiceUnavailable',
        ]
        
        error_type = type(error).__name__
        if error_type in transient_types:
            return True
        
        return False
    
    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Backoff delay in seconds
        """
        backoff = min(
            self.config.initial_backoff_seconds * (2 ** attempt),
            self.config.max_backoff_seconds
        )
        return backoff
