"""
Synthetic Data Generator for Automated LLM Finetuning Pipeline

This module provides the SyntheticDataGenerator class for generating training data
using Claude Sonnet 4 via AWS Bedrock based on use case descriptions.

The SyntheticDataGenerator handles:
- Generating training examples using Claude Sonnet 4
- Batch processing for efficient data generation
- Progress saving for resumption after interruptions
- Dataset analysis and training parameter recommendations
- Unicode cleaning and JSON validation
"""

import json
import logging
import os
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from src.config_models import DatasetAnalysis, PipelineConfig, TrainingExample, UseCase
from src.logging_config import get_logger

# Configure module logger
logger = get_logger(__name__)


class SyntheticDataGenerator:
    """
    Generates synthetic training data using Claude Sonnet 4 via AWS Bedrock.
    
    The SyntheticDataGenerator uses Claude Sonnet 4 to generate high-quality
    training examples based on use case descriptions. It supports:
    - Batch processing for efficient generation
    - Progress saving to enable resumption
    - Dataset analysis for training parameter recommendations
    - Data quality validation (JSONL format, ASCII compliance)
    
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
        >>> # Create generator
        >>> generator = SyntheticDataGenerator(bedrock_client, pipeline_config)
        >>> 
        >>> # Generate training data
        >>> use_case = config_manager.load_use_case("customer_support")
        >>> data_path = generator.generate_training_data(use_case, num_examples=1000)
    """
    
    def __init__(
        self,
        bedrock_client: Any,
        config: PipelineConfig
    ):
        """
        Initialize SyntheticDataGenerator with Bedrock client and configuration.
        
        Sets up the generator with the necessary AWS Bedrock client for calling
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
            >>> generator = SyntheticDataGenerator(bedrock_client, pipeline_config)
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
            "SyntheticDataGenerator initialized",
            extra={
                "context": {
                    "model_id": self.model_id,
                    "region": self.config.aws_region,
                    "max_retries": self.config.max_retries,
                }
            }
        )
        
        logger.debug(
            "SyntheticDataGenerator configuration details",
            extra={
                "context": {
                    "bedrock_model_id": self.config.bedrock_model_id,
                    "initial_backoff_seconds": self.config.initial_backoff_seconds,
                    "max_backoff_seconds": self.config.max_backoff_seconds,
                }
            }
        )

    def generate_training_data(
        self,
        use_case: UseCase,
        num_examples: int = 1000,
        batch_size: int = 50
    ) -> str:
        """
        Generate training data and return path to JSONL file.
        
        Generates synthetic training examples using Claude Sonnet 4 via AWS Bedrock
        based on the use case description and data generation prompt. Examples are
        generated in batches for efficiency, with progress saved incrementally after
        each batch to enable resumption after interruptions.
        
        The generated data is saved in JSONL format (one JSON object per line) with
        each example containing instruction, context, and response fields. Unicode
        characters are cleaned to ensure ASCII compliance, and JSON validation is
        performed on each example.
        
        Args:
            use_case: UseCase instance containing description, data generation prompt,
                     and other configuration for generating training examples.
            num_examples: Total number of training examples to generate. Default is 1000.
                         Must be a positive integer.
            batch_size: Number of examples to generate in each batch. Default is 50.
                       Smaller batches provide more frequent progress saves but may
                       be less efficient. Must be a positive integer.
        
        Returns:
            str: Path to the generated JSONL file containing all training examples.
                The file is saved in event_files/training_data/ directory with a
                timestamped filename: {use_case_name}_{timestamp}.jsonl
        
        Raises:
            ValueError: If num_examples or batch_size is not positive
            RuntimeError: If data generation fails after all retry attempts
            IOError: If unable to write to the output file
        
        Example:
            >>> from src.aws_client_manager import AWSClientManager
            >>> from src.configuration_manager import ConfigurationManager
            >>> 
            >>> config_manager = ConfigurationManager()
            >>> pipeline_config = config_manager.load_pipeline_config()
            >>> use_case = config_manager.load_use_case("customer_support")
            >>> 
            >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
            >>> bedrock_client = aws_manager.get_bedrock_runtime_client()
            >>> 
            >>> generator = SyntheticDataGenerator(bedrock_client, pipeline_config)
            >>> data_path = generator.generate_training_data(use_case, num_examples=500)
            >>> print(f"Training data saved to: {data_path}")
        """
        # Validate parameters
        if num_examples <= 0:
            raise ValueError(f"num_examples must be positive, got {num_examples}")
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")
        
        logger.info(
            "Starting training data generation",
            extra={
                "context": {
                    "use_case": use_case.name,
                    "num_examples": num_examples,
                    "batch_size": batch_size,
                }
            }
        )
        
        # Create output directory if it doesn't exist
        output_dir = Path("event_files/training_data")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{use_case.name}_{timestamp}.jsonl"
        
        # Calculate number of batches
        num_batches = (num_examples + batch_size - 1) // batch_size
        
        logger.info(
            "Data generation plan",
            extra={
                "context": {
                    "output_path": str(output_path),
                    "num_batches": num_batches,
                    "examples_per_batch": batch_size,
                }
            }
        )
        
        # Generate examples in batches
        total_generated = 0
        for batch_num in range(num_batches):
            # Calculate examples for this batch (last batch may be smaller)
            examples_in_batch = min(batch_size, num_examples - total_generated)
            
            logger.info(
                f"Generating batch {batch_num + 1}/{num_batches}",
                extra={
                    "context": {
                        "batch_num": batch_num + 1,
                        "total_batches": num_batches,
                        "examples_in_batch": examples_in_batch,
                        "total_generated": total_generated,
                    }
                }
            )
            
            # Generate batch with retry logic
            batch_examples = self._generate_batch(
                use_case.data_generation_prompt,
                use_case.description,
                examples_in_batch
            )
            
            # Save progress incrementally
            self._save_progress(batch_examples, str(output_path))
            
            total_generated += len(batch_examples)
            
            logger.info(
                f"Batch {batch_num + 1} completed",
                extra={
                    "context": {
                        "batch_num": batch_num + 1,
                        "examples_generated": len(batch_examples),
                        "total_generated": total_generated,
                        "progress_percent": (total_generated / num_examples) * 100,
                    }
                }
            )
        
        logger.info(
            "Training data generation completed",
            extra={
                "context": {
                    "use_case": use_case.name,
                    "total_examples": total_generated,
                    "output_path": str(output_path),
                }
            }
        )
        
        return str(output_path)
    
    def _generate_batch(
        self,
        data_generation_prompt: str,
        use_case_description: str,
        batch_size: int
    ) -> List[TrainingExample]:
        """
        Generate a single batch of training examples using Claude Sonnet 4.
        
        Calls AWS Bedrock to invoke Claude Sonnet 4 with the data generation prompt
        and use case description. Implements exponential backoff retry logic for
        transient errors. Validates and cleans the generated examples.
        
        Args:
            data_generation_prompt: Prompt template for data generation
            use_case_description: Description of the use case domain
            batch_size: Number of examples to generate in this batch
        
        Returns:
            List[TrainingExample]: List of validated training examples
        
        Raises:
            RuntimeError: If generation fails after all retry attempts
        """
        # Construct the full prompt for Claude
        full_prompt = f"""{data_generation_prompt}

Use Case Description:
{use_case_description}

Generate exactly {batch_size} training examples. Each example should be in JSON format with the following structure:
{{
    "instruction": "The instruction or task description",
    "context": "Any relevant context or background information",
    "response": "The ideal response or completion"
}}

Return ONLY a JSON array of examples, with no additional text or explanation. Example format:
[
    {{"instruction": "...", "context": "...", "response": "..."}},
    {{"instruction": "...", "context": "...", "response": "..."}}
]
"""
        
        # Retry with exponential backoff
        for attempt in range(self.config.max_retries):
            try:
                logger.debug(
                    f"Calling Bedrock API (attempt {attempt + 1}/{self.config.max_retries})",
                    extra={
                        "context": {
                            "model_id": self.model_id,
                            "batch_size": batch_size,
                            "attempt": attempt + 1,
                        }
                    }
                )
                
                # Prepare request body for Claude
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": full_prompt
                        }
                    ],
                    "temperature": 0.7,
                }
                
                # Invoke Bedrock
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                content = response_body['content'][0]['text']
                
                # Extract JSON array from response
                # Claude might wrap the JSON in markdown code blocks
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]  # Remove ```json
                if content.startswith('```'):
                    content = content[3:]  # Remove ```
                if content.endswith('```'):
                    content = content[:-3]  # Remove trailing ```
                content = content.strip()
                
                # Parse JSON array
                examples_data = json.loads(content)
                
                if not isinstance(examples_data, list):
                    raise ValueError("Response is not a JSON array")
                
                # Convert to TrainingExample objects with validation and cleaning
                examples = []
                for example_data in examples_data:
                    # Clean unicode characters
                    cleaned_data = {
                        'instruction': self._clean_unicode(example_data.get('instruction', '')),
                        'context': self._clean_unicode(example_data.get('context', '')),
                        'response': self._clean_unicode(example_data.get('response', ''))
                    }
                    
                    # Validate required fields
                    if not cleaned_data['instruction'] or not cleaned_data['response']:
                        logger.warning(
                            "Skipping example with missing required fields",
                            extra={"context": {"example": cleaned_data}}
                        )
                        continue
                    
                    examples.append(TrainingExample(**cleaned_data))
                
                logger.info(
                    f"Successfully generated {len(examples)} examples",
                    extra={
                        "context": {
                            "requested": batch_size,
                            "generated": len(examples),
                        }
                    }
                )
                
                return examples
                
            except Exception as e:
                logger.warning(
                    f"Batch generation attempt {attempt + 1} failed: {e}",
                    extra={
                        "context": {
                            "attempt": attempt + 1,
                            "max_retries": self.config.max_retries,
                            "error": str(e),
                        }
                    }
                )
                
                # If this was the last attempt, raise the error
                if attempt == self.config.max_retries - 1:
                    logger.error(
                        "Batch generation failed after all retry attempts",
                        extra={
                            "context": {
                                "max_retries": self.config.max_retries,
                                "final_error": str(e),
                            }
                        }
                    )
                    raise RuntimeError(
                        f"Failed to generate batch after {self.config.max_retries} attempts: {e}"
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
        raise RuntimeError("Unexpected error in batch generation")
    
    def _save_progress(
        self,
        examples: List[TrainingExample],
        output_path: str
    ) -> None:
        """
        Append training examples to JSONL file for incremental progress saving.
        
        Saves examples in JSONL format (one JSON object per line) to enable
        resumption after interruptions. Each example is validated before writing.
        
        Args:
            examples: List of TrainingExample objects to save
            output_path: Path to the output JSONL file
        
        Raises:
            IOError: If unable to write to the output file
            ValueError: If examples contain invalid data
        """
        try:
            logger.debug(
                f"Saving {len(examples)} examples to {output_path}",
                extra={
                    "context": {
                        "num_examples": len(examples),
                        "output_path": output_path,
                    }
                }
            )
            
            # Append to file (create if doesn't exist)
            with open(output_path, 'a', encoding='utf-8') as f:
                for example in examples:
                    # Convert to dict and validate JSON serialization
                    example_dict = example.to_dict()
                    
                    # Ensure all fields are present and non-empty
                    if not example_dict.get('instruction') or not example_dict.get('response'):
                        logger.warning(
                            "Skipping invalid example during save",
                            extra={"context": {"example": example_dict}}
                        )
                        continue
                    
                    # Write as single line JSON
                    json_line = json.dumps(example_dict, ensure_ascii=True)
                    f.write(json_line + '\n')
            
            logger.debug(
                f"Successfully saved {len(examples)} examples",
                extra={"context": {"output_path": output_path}}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to save progress: {e}",
                extra={
                    "context": {
                        "output_path": output_path,
                        "num_examples": len(examples),
                        "error": str(e),
                    }
                }
            )
            raise IOError(f"Failed to save progress to {output_path}: {e}")
    
    def analyze_dataset(self, dataset_path: str) -> DatasetAnalysis:
        """
        Analyze dataset size and recommend training parameters.
        
        Reads a JSONL training dataset file and computes statistics including
        the number of examples, average instruction length, and average response
        length. Based on the dataset size, recommends optimal training parameters
        such as number of epochs and batch size.
        
        The recommendations follow these heuristics:
        - Larger datasets (>1000 examples): Fewer epochs (3-5), larger batch sizes (16-32)
        - Medium datasets (500-1000 examples): Medium epochs (5-7), medium batch sizes (8-16)
        - Smaller datasets (<500 examples): More epochs (7-10), smaller batch sizes (4-8)
        - Batch sizes are always powers of 2 for optimal GPU utilization
        
        Args:
            dataset_path: Path to the JSONL file containing training examples.
                         Each line should be a JSON object with 'instruction',
                         'context', and 'response' fields.
        
        Returns:
            DatasetAnalysis: Analysis results containing:
                - num_examples: Total number of training examples
                - avg_instruction_length: Average character length of instructions
                - avg_response_length: Average character length of responses
                - recommended_epochs: Recommended number of training epochs
                - recommended_batch_size: Recommended batch size (power of 2)
        
        Raises:
            FileNotFoundError: If dataset_path does not exist
            ValueError: If dataset file is empty or contains invalid JSON
            IOError: If unable to read the dataset file
        
        Example:
            >>> from src.aws_client_manager import AWSClientManager
            >>> from src.configuration_manager import ConfigurationManager
            >>> 
            >>> config_manager = ConfigurationManager()
            >>> pipeline_config = config_manager.load_pipeline_config()
            >>> aws_manager = AWSClientManager({'region': pipeline_config.aws_region})
            >>> bedrock_client = aws_manager.get_bedrock_runtime_client()
            >>> 
            >>> generator = SyntheticDataGenerator(bedrock_client, pipeline_config)
            >>> analysis = generator.analyze_dataset("event_files/training_data/dataset.jsonl")
            >>> print(f"Examples: {analysis.num_examples}")
            >>> print(f"Recommended epochs: {analysis.recommended_epochs}")
            >>> print(f"Recommended batch size: {analysis.recommended_batch_size}")
        """
        # Validate dataset path exists
        dataset_file = Path(dataset_path)
        if not dataset_file.exists():
            logger.error(
                f"Dataset file not found: {dataset_path}",
                extra={"context": {"dataset_path": dataset_path}}
            )
            raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
        
        logger.info(
            "Starting dataset analysis",
            extra={"context": {"dataset_path": dataset_path}}
        )
        
        # Initialize counters
        num_examples = 0
        total_instruction_length = 0
        total_response_length = 0
        
        try:
            # Read and analyze JSONL file
            with open(dataset_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    try:
                        # Parse JSON
                        example = json.loads(line)
                        
                        # Validate required fields
                        if 'instruction' not in example or 'response' not in example:
                            logger.warning(
                                f"Skipping line {line_num}: missing required fields",
                                extra={
                                    "context": {
                                        "line_num": line_num,
                                        "has_instruction": 'instruction' in example,
                                        "has_response": 'response' in example,
                                    }
                                }
                            )
                            continue
                        
                        # Count example
                        num_examples += 1
                        
                        # Accumulate lengths
                        instruction = example.get('instruction', '')
                        response = example.get('response', '')
                        
                        total_instruction_length += len(instruction)
                        total_response_length += len(response)
                        
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Skipping line {line_num}: invalid JSON",
                            extra={
                                "context": {
                                    "line_num": line_num,
                                    "error": str(e),
                                }
                            }
                        )
                        continue
            
            # Validate we found at least one example
            if num_examples == 0:
                logger.error(
                    "Dataset file is empty or contains no valid examples",
                    extra={"context": {"dataset_path": dataset_path}}
                )
                raise ValueError(
                    f"Dataset file is empty or contains no valid examples: {dataset_path}"
                )
            
            # Calculate averages
            avg_instruction_length = total_instruction_length // num_examples
            avg_response_length = total_response_length // num_examples
            
            # Recommend training parameters based on dataset size
            if num_examples >= 1000:
                # Large dataset: fewer epochs, larger batch size
                recommended_epochs = 3
                recommended_batch_size = 32
            elif num_examples >= 500:
                # Medium dataset: medium epochs, medium batch size
                recommended_epochs = 5
                recommended_batch_size = 16
            elif num_examples >= 200:
                # Small-medium dataset: more epochs, smaller batch size
                recommended_epochs = 7
                recommended_batch_size = 8
            else:
                # Small dataset: most epochs, smallest batch size
                recommended_epochs = 10
                recommended_batch_size = 4
            
            # Create analysis result
            analysis = DatasetAnalysis(
                num_examples=num_examples,
                avg_instruction_length=avg_instruction_length,
                avg_response_length=avg_response_length,
                recommended_epochs=recommended_epochs,
                recommended_batch_size=recommended_batch_size
            )
            
            logger.info(
                "Dataset analysis completed",
                extra={
                    "context": {
                        "num_examples": num_examples,
                        "avg_instruction_length": avg_instruction_length,
                        "avg_response_length": avg_response_length,
                        "recommended_epochs": recommended_epochs,
                        "recommended_batch_size": recommended_batch_size,
                    }
                }
            )
            
            return analysis
            
        except FileNotFoundError:
            # Re-raise FileNotFoundError as-is
            raise
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to analyze dataset: {e}",
                extra={
                    "context": {
                        "dataset_path": dataset_path,
                        "error": str(e),
                    }
                }
            )
            raise IOError(f"Failed to analyze dataset {dataset_path}: {e}")
    
    def _clean_unicode(self, text: str) -> str:
        """
        Clean unicode characters to ensure ASCII compliance.
        
        Normalizes unicode characters and removes or replaces non-ASCII characters
        to ensure compatibility with training systems that may not support full unicode.
        
        Args:
            text: Input text that may contain unicode characters
        
        Returns:
            str: Cleaned text with ASCII-compatible characters
        """
        if not text:
            return text
        
        # Normalize unicode to decomposed form
        normalized = unicodedata.normalize('NFKD', text)
        
        # Encode to ASCII, replacing non-ASCII characters
        # Use 'ignore' to remove characters that can't be encoded
        ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
        
        return ascii_text
    
    def validate_jsonl_format(self, file_path: str) -> tuple[bool, List[str]]:
        """
        Validate that a file is in proper JSONL format.
        
        Checks that:
        - File exists and is readable
        - Each non-empty line is valid JSON
        - File is not empty
        
        Args:
            file_path: Path to the JSONL file to validate
        
        Returns:
            tuple[bool, List[str]]: (is_valid, list of error messages)
                - is_valid: True if file is valid JSONL, False otherwise
                - errors: List of error messages describing validation failures
        
        Example:
            >>> generator = SyntheticDataGenerator(bedrock_client, config)
            >>> is_valid, errors = generator.validate_jsonl_format("data.jsonl")
            >>> if not is_valid:
            ...     print(f"Validation errors: {errors}")
        """
        errors = []
        
        # Check file exists
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            errors.append(f"File does not exist: {file_path}")
            return False, errors
        
        # Check file is readable
        if not file_path_obj.is_file():
            errors.append(f"Path is not a file: {file_path}")
            return False, errors
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # Check file is not empty
                non_empty_lines = [line for line in lines if line.strip()]
                if not non_empty_lines:
                    errors.append("File is empty or contains only whitespace")
                    return False, errors
                
                # Validate each line is valid JSON
                for line_num, line in enumerate(lines, start=1):
                    line = line.strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        errors.append(
                            f"Line {line_num}: Invalid JSON - {str(e)}"
                        )
        
        except Exception as e:
            errors.append(f"Error reading file: {str(e)}")
            return False, errors
        
        # Return validation result
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_ascii_compliance(self, text: str) -> tuple[bool, List[str]]:
        """
        Check if text contains only ASCII characters.
        
        Validates that all characters in the text are within the ASCII
        character set (0-127). Non-ASCII characters may cause issues with
        some training systems.
        
        Args:
            text: Text string to validate
        
        Returns:
            tuple[bool, List[str]]: (is_compliant, list of issues)
                - is_compliant: True if text is ASCII-only, False otherwise
                - issues: List of descriptions of non-ASCII characters found
        
        Example:
            >>> generator = SyntheticDataGenerator(bedrock_client, config)
            >>> is_ascii, issues = generator.validate_ascii_compliance("Hello world")
            >>> assert is_ascii and len(issues) == 0
            >>> 
            >>> is_ascii, issues = generator.validate_ascii_compliance("Café")
            >>> assert not is_ascii and len(issues) > 0
        """
        issues: List[str] = []
        
        if not text:
            return True, issues
        
        # Check each character
        non_ascii_chars = set()
        for i, char in enumerate(text):
            if ord(char) > 127:
                non_ascii_chars.add(char)
        
        if non_ascii_chars:
            issues.append(
                f"Found {len(non_ascii_chars)} non-ASCII character(s): "
                f"{', '.join(repr(c) for c in sorted(non_ascii_chars))}"
            )
            return False, issues
        
        return True, issues
    
    def validate_field_completeness(
        self,
        example: dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        Validate that a training example has all required fields.
        
        Checks that the example dictionary contains:
        - 'instruction' field (non-empty string)
        - 'context' field (can be empty string)
        - 'response' field (non-empty string)
        
        Args:
            example: Dictionary representing a training example
        
        Returns:
            tuple[bool, List[str]]: (is_complete, list of missing/invalid fields)
                - is_complete: True if all required fields are present and valid
                - errors: List of error messages for missing or invalid fields
        
        Example:
            >>> generator = SyntheticDataGenerator(bedrock_client, config)
            >>> example = {
            ...     "instruction": "Help the user",
            ...     "context": "User needs assistance",
            ...     "response": "I'm here to help"
            ... }
            >>> is_complete, errors = generator.validate_field_completeness(example)
            >>> assert is_complete and len(errors) == 0
        """
        errors = []
        
        # Check required fields exist
        required_fields = ['instruction', 'context', 'response']
        for field in required_fields:
            if field not in example:
                errors.append(f"Missing required field: '{field}'")
        
        # If fields are missing, return early
        if errors:
            return False, errors
        
        # Validate field types and content
        if not isinstance(example['instruction'], str):
            errors.append(
                f"Field 'instruction' must be a string, got {type(example['instruction']).__name__}"
            )
        elif not example['instruction'].strip():
            errors.append("Field 'instruction' cannot be empty")
        
        if not isinstance(example['context'], str):
            errors.append(
                f"Field 'context' must be a string, got {type(example['context']).__name__}"
            )
        # Note: context can be empty, so we don't check for emptiness
        
        if not isinstance(example['response'], str):
            errors.append(
                f"Field 'response' must be a string, got {type(example['response']).__name__}"
            )
        elif not example['response'].strip():
            errors.append("Field 'response' cannot be empty")
        
        is_complete = len(errors) == 0
        return is_complete, errors
    
    def detect_duplicates(
        self,
        examples: List[TrainingExample]
    ) -> List[tuple[int, int]]:
        """
        Detect duplicate training examples in a list.
        
        Identifies examples that have identical instruction, context, and response
        fields. Returns pairs of indices where duplicates are found.
        
        Args:
            examples: List of TrainingExample objects to check for duplicates
        
        Returns:
            List[tuple[int, int]]: List of (index1, index2) tuples where
                examples[index1] is a duplicate of examples[index2].
                Only returns pairs where index1 < index2 to avoid reporting
                the same duplicate twice.
        
        Example:
            >>> generator = SyntheticDataGenerator(bedrock_client, config)
            >>> examples = [
            ...     TrainingExample("Q1", "C1", "R1"),
            ...     TrainingExample("Q2", "C2", "R2"),
            ...     TrainingExample("Q1", "C1", "R1"),  # Duplicate of index 0
            ... ]
            >>> duplicates = generator.detect_duplicates(examples)
            >>> assert (0, 2) in duplicates
        """
        duplicates = []
        
        # Create a dictionary to track seen examples
        # Key: (instruction, context, response) tuple
        # Value: list of indices where this example appears
        seen: dict[tuple[str, str, str], List[int]] = {}
        
        for i, example in enumerate(examples):
            # Create a hashable key from the example
            key = (
                example.instruction,
                example.context,
                example.response
            )
            
            if key in seen:
                # Found a duplicate - record all pairs with previous occurrences
                for prev_index in seen[key]:
                    duplicates.append((prev_index, i))
            else:
                seen[key] = []
            
            seen[key].append(i)
        
        return duplicates
    
    def remove_duplicates(
        self,
        examples: List[TrainingExample]
    ) -> List[TrainingExample]:
        """
        Remove duplicate training examples from a list.
        
        Returns a new list containing only unique examples, preserving the
        order of first occurrence. Examples are considered duplicates if they
        have identical instruction, context, and response fields.
        
        Args:
            examples: List of TrainingExample objects that may contain duplicates
        
        Returns:
            List[TrainingExample]: New list with duplicates removed, maintaining
                the order of first occurrence
        
        Example:
            >>> generator = SyntheticDataGenerator(bedrock_client, config)
            >>> examples = [
            ...     TrainingExample("Q1", "C1", "R1"),
            ...     TrainingExample("Q2", "C2", "R2"),
            ...     TrainingExample("Q1", "C1", "R1"),  # Duplicate
            ...     TrainingExample("Q3", "C3", "R3"),
            ... ]
            >>> unique = generator.remove_duplicates(examples)
            >>> assert len(unique) == 3
        """
        seen = set()
        unique_examples = []
        
        for example in examples:
            # Create a hashable key from the example
            key = (
                example.instruction,
                example.context,
                example.response
            )
            
            if key not in seen:
                seen.add(key)
                unique_examples.append(example)
        
        logger.info(
            f"Removed {len(examples) - len(unique_examples)} duplicate examples",
            extra={
                "context": {
                    "original_count": len(examples),
                    "unique_count": len(unique_examples),
                    "duplicates_removed": len(examples) - len(unique_examples),
                }
            }
        )
        
        return unique_examples
