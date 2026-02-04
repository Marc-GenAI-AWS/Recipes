"""
Configuration Manager for Automated LLM Finetuning Pipeline

This module provides the ConfigurationManager class for loading, validating,
and managing use case definitions and pipeline configurations.

The ConfigurationManager handles:
- Loading use case definitions from YAML files
- Saving use cases with versioning support
- Loading pipeline configuration
- Validating configuration completeness and correctness
- Managing configuration file organization
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

import yaml

from src.config_models import (
    UseCase,
    PipelineConfig,
    ValidationResult,
    UseCasePydantic,
    PipelineConfigPydantic
)

# Configure module logger
logger = logging.getLogger(__name__)


class ConfigurationManager:
    """
    Manages use case definitions and pipeline configurations.
    
    The ConfigurationManager provides methods to load, save, and validate
    configuration files for the finetuning pipeline. It handles:
    - Use case YAML files in the use_cases subdirectory
    - Pipeline configuration YAML files
    - Configuration validation and versioning
    - Directory structure management
    
    Attributes:
        config_dir: Root configuration directory path
        use_cases_dir: Directory containing use case YAML files
        pipeline_config_path: Path to pipeline configuration file
    """
    
    def __init__(self, config_dir: str = "config/"):
        """
        Initialize ConfigurationManager with configuration directory.
        
        Creates the configuration directory structure if it doesn't exist:
        - config/
        - config/use_cases/
        
        Args:
            config_dir: Root directory for configuration files.
                       Defaults to "config/" relative to current working directory.
        
        Raises:
            ValueError: If config_dir is empty or invalid
            OSError: If directory creation fails due to permissions
        
        Example:
            >>> config_manager = ConfigurationManager()
            >>> config_manager = ConfigurationManager("custom_config/")
        """
        # Validate config_dir parameter
        if not config_dir or not config_dir.strip():
            raise ValueError("config_dir cannot be empty")
        
        # Normalize path and convert to Path object
        self.config_dir = Path(config_dir.strip()).resolve()
        
        # Set up subdirectories
        self.use_cases_dir = self.config_dir / "use_cases"
        
        # Default pipeline config path (can be overridden by load_pipeline_config)
        self.pipeline_config_path = self.config_dir / "pipeline_config.yaml"
        
        # Create directory structure if it doesn't exist
        self._initialize_directories()
        
        logger.info(
            f"ConfigurationManager initialized with config_dir: {self.config_dir}"
        )
        logger.debug(f"Use cases directory: {self.use_cases_dir}")
        logger.debug(f"Pipeline config path: {self.pipeline_config_path}")
    
    def _initialize_directories(self) -> None:
        """
        Create configuration directory structure if it doesn't exist.
        
        Creates:
        - config_dir (root configuration directory)
        - use_cases_dir (subdirectory for use case YAML files)
        
        Raises:
            OSError: If directory creation fails due to permissions or disk space
        """
        try:
            # Create root config directory
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured config directory exists: {self.config_dir}")
            
            # Create use_cases subdirectory
            self.use_cases_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured use_cases directory exists: {self.use_cases_dir}")
            
        except OSError as e:
            error_msg = (
                f"Failed to create configuration directories: {e}. "
                f"Check permissions for path: {self.config_dir}"
            )
            logger.error(error_msg)
            raise OSError(error_msg) from e
    
    def load_use_case(self, name: str) -> UseCase:
        """
        Load use case definition from YAML file.
        
        Reads a use case configuration from the use_cases subdirectory
        and converts it to a UseCase dataclass instance. The method handles
        YAML parsing, field validation, and type conversion.
        
        Args:
            name: Name of the use case to load (without .yaml extension).
                  Can include or exclude the .yaml extension.
        
        Returns:
            UseCase: Loaded and validated use case definition
        
        Raises:
            ValueError: If name is empty or invalid
            FileNotFoundError: If use case file doesn't exist
            yaml.YAMLError: If YAML file is malformed
            KeyError: If required fields are missing from YAML
            TypeError: If field types are incorrect
        
        Example:
            >>> config_manager = ConfigurationManager()
            >>> use_case = config_manager.load_use_case("customer_support")
            >>> print(use_case.name)
            'customer_support'
        """
        # Validate name parameter
        if not name or not name.strip():
            raise ValueError("Use case name cannot be empty")
        
        name = name.strip()
        
        # Remove .yaml extension if provided
        if name.endswith('.yaml'):
            name = name[:-5]
        
        # Construct file path
        use_case_path = self.use_cases_dir / f"{name}.yaml"
        
        logger.info(f"Loading use case '{name}' from {use_case_path}")
        
        # Check if file exists
        if not use_case_path.exists():
            error_msg = (
                f"Use case file not found: {use_case_path}. "
                f"Available use cases: {', '.join(self.list_use_cases()) or 'none'}"
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Read and parse YAML file
        try:
            with open(use_case_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            logger.debug(f"Successfully parsed YAML from {use_case_path}")
            
        except yaml.YAMLError as e:
            error_msg = f"Failed to parse YAML file {use_case_path}: {e}"
            logger.error(error_msg)
            raise yaml.YAMLError(error_msg) from e
        
        except IOError as e:
            error_msg = f"Failed to read file {use_case_path}: {e}"
            logger.error(error_msg)
            raise IOError(error_msg) from e
        
        # Validate that yaml_data is a dictionary
        if not isinstance(yaml_data, dict):
            raise TypeError(
                f"YAML file must contain a dictionary, got {type(yaml_data).__name__}"
            )
        
        # Extract and validate required fields
        try:
            # Required fields
            use_case_name = yaml_data['name']
            description = yaml_data['description']
            test_questions = yaml_data['test_questions']
            judge_criteria = yaml_data['judge_criteria']
            data_generation_prompt = yaml_data['data_generation_prompt']
            judge_prompt = yaml_data['judge_prompt']
            
            # Optional fields with defaults
            version = yaml_data.get('version', 1)
            
            # Handle created_at field
            created_at_raw = yaml_data.get('created_at')
            if created_at_raw is None:
                created_at = datetime.now()
            elif isinstance(created_at_raw, datetime):
                created_at = created_at_raw
            elif isinstance(created_at_raw, str):
                # Parse ISO format datetime string
                try:
                    created_at = datetime.fromisoformat(created_at_raw.replace('Z', '+00:00'))
                except ValueError as e:
                    logger.warning(
                        f"Failed to parse created_at '{created_at_raw}', using current time: {e}"
                    )
                    created_at = datetime.now()
            else:
                logger.warning(
                    f"Invalid created_at type {type(created_at_raw)}, using current time"
                )
                created_at = datetime.now()
            
            # Validate test_questions is a list
            if not isinstance(test_questions, list):
                raise TypeError(
                    f"test_questions must be a list, got {type(test_questions).__name__}"
                )
            
            # Create UseCase instance (validation happens in __post_init__)
            use_case = UseCase(
                name=use_case_name,
                description=description,
                test_questions=test_questions,
                judge_criteria=judge_criteria,
                data_generation_prompt=data_generation_prompt,
                judge_prompt=judge_prompt,
                version=version,
                created_at=created_at
            )
            
            logger.info(
                f"Successfully loaded use case '{use_case.name}' "
                f"(version {use_case.version}, {len(use_case.test_questions)} questions)"
            )
            
            return use_case
            
        except KeyError as e:
            error_msg = (
                f"Missing required field in use case YAML: {e}. "
                f"Required fields: name, description, test_questions, judge_criteria, "
                f"data_generation_prompt, judge_prompt"
            )
            logger.error(error_msg)
            raise KeyError(error_msg) from e
        
        except (ValueError, TypeError) as e:
            # Re-raise validation errors from UseCase.__post_init__
            error_msg = f"Invalid use case data in {use_case_path}: {e}"
            logger.error(error_msg)
            raise type(e)(error_msg) from e
    
    def save_use_case(self, use_case: UseCase) -> None:
        """
        Save use case definition to YAML file with versioning support.
        
        When a use case is updated (already exists), the method preserves
        the previous version by creating a backup with timestamp before
        saving the new version. The version number is automatically
        incremented for updates.
        
        Versioning behavior:
        - New use case: Saved as {name}.yaml with version 1
        - Updated use case: Previous version backed up as {name}.v{N}.{timestamp}.yaml,
          new version saved with incremented version number
        
        Args:
            use_case: UseCase instance to save
        
        Raises:
            ValueError: If use_case is None or has invalid data
            OSError: If file write fails due to permissions or disk space
            yaml.YAMLError: If YAML serialization fails
        
        Example:
            >>> config_manager = ConfigurationManager()
            >>> use_case = UseCase(
            ...     name="customer_support",
            ...     description="Customer support use case",
            ...     test_questions=["Question 1"],
            ...     judge_criteria="Criteria",
            ...     data_generation_prompt="Prompt",
            ...     judge_prompt="Judge prompt"
            ... )
            >>> config_manager.save_use_case(use_case)
        """
        # Validate use_case parameter
        if use_case is None:
            raise ValueError("use_case cannot be None")
        
        # Validate use_case has required attributes (triggers __post_init__ validation)
        if not hasattr(use_case, 'name') or not use_case.name:
            raise ValueError("use_case must have a valid name")
        
        # Construct file path
        use_case_path = self.use_cases_dir / f"{use_case.name}.yaml"
        
        logger.info(f"Saving use case '{use_case.name}' to {use_case_path}")
        
        # Check if use case already exists (for versioning)
        if use_case_path.exists():
            logger.info(f"Use case '{use_case.name}' already exists, creating backup")
            
            try:
                # Load existing use case to get current version
                existing_use_case = self.load_use_case(use_case.name)
                
                # Create backup filename with version and timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{use_case.name}.v{existing_use_case.version}.{timestamp}.yaml"
                backup_path = self.use_cases_dir / backup_filename
                
                # Copy existing file to backup
                import shutil
                shutil.copy2(use_case_path, backup_path)
                
                logger.info(f"Created backup: {backup_filename}")
                
                # Increment version for new save
                use_case.version = existing_use_case.version + 1
                logger.debug(f"Incremented version to {use_case.version}")
                
            except Exception as e:
                # Log warning but continue with save (backup is best-effort)
                logger.warning(f"Failed to create backup for '{use_case.name}': {e}")
                # Still increment version if we can determine it
                if hasattr(e, '__cause__') and not isinstance(e.__cause__, FileNotFoundError):
                    # If load failed for reasons other than file not found, increment anyway
                    use_case.version = use_case.version + 1
        
        # Convert UseCase to dictionary for YAML serialization
        use_case_dict = {
            'name': use_case.name,
            'description': use_case.description,
            'test_questions': use_case.test_questions,
            'judge_criteria': use_case.judge_criteria,
            'data_generation_prompt': use_case.data_generation_prompt,
            'judge_prompt': use_case.judge_prompt,
            'version': use_case.version,
            'created_at': use_case.created_at.isoformat()
        }
        
        # Write to YAML file
        try:
            # Write to temporary file first for atomic operation
            temp_path = use_case_path.with_suffix('.yaml.tmp')
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    use_case_dict,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False
                )
            
            # Atomic rename (overwrites existing file)
            import shutil
            shutil.move(str(temp_path), str(use_case_path))
            
            logger.info(
                f"Successfully saved use case '{use_case.name}' "
                f"(version {use_case.version})"
            )
            
        except yaml.YAMLError as e:
            error_msg = f"Failed to serialize use case to YAML: {e}"
            logger.error(error_msg)
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise yaml.YAMLError(error_msg) from e
        
        except OSError as e:
            error_msg = (
                f"Failed to write use case file {use_case_path}: {e}. "
                f"Check permissions and disk space."
            )
            logger.error(error_msg)
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise OSError(error_msg) from e
        
        except Exception as e:
            error_msg = f"Unexpected error saving use case: {e}"
            logger.error(error_msg)
            # Clean up temp file if it exists
            if 'temp_path' in locals() and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise
    
    def list_use_cases(self) -> List[str]:
        """
        Return names of all available use cases.
        
        Scans the use_cases directory for YAML files and returns their names
        (without the .yaml extension). Excludes versioned backup files
        (files matching pattern *.v{N}.{timestamp}.yaml).
        
        Returns:
            List[str]: List of use case names (sorted alphabetically)
        
        Example:
            >>> config_manager = ConfigurationManager()
            >>> use_cases = config_manager.list_use_cases()
            >>> print(use_cases)
            ['code_review', 'customer_support']
        """
        try:
            # Find all .yaml files in use_cases directory
            yaml_files = list(self.use_cases_dir.glob("*.yaml"))
            
            # Extract names (remove .yaml extension) and filter out backups
            use_case_names = []
            for f in yaml_files:
                stem = f.stem
                # Skip backup files (format: name.v{N}.{timestamp})
                # Check if stem contains ".v" followed by digits
                if '.v' in stem and any(part.startswith('v') and part[1:].split('.')[0].isdigit() 
                                       for part in stem.split('.')):
                    logger.debug(f"Skipping backup file: {f.name}")
                    continue
                use_case_names.append(stem)
            
            # Sort alphabetically
            use_case_names.sort()
            
            logger.debug(f"Found {len(use_case_names)} use cases: {use_case_names}")
            
            return use_case_names
            
        except Exception as e:
            logger.error(f"Failed to list use cases: {e}")
            return []
    
    def load_pipeline_config(self, config_name: str = "pipeline_config") -> PipelineConfig:
        """
        Load pipeline configuration from YAML file.
        
        Reads pipeline configuration including AWS settings, training parameters,
        inference settings, and pipeline thresholds. Supports environment-specific
        configurations (e.g., pipeline_config.dev.yaml, pipeline_config.prod.yaml).
        
        The method searches for configuration files in the following order:
        1. {config_name}.yaml (exact match)
        2. pipeline_config.{config_name}.yaml (environment-specific)
        3. pipeline_config.yaml (default fallback)
        
        Args:
            config_name: Name of the configuration to load (without .yaml extension).
                        Can be a simple name like "pipeline_config" or an environment
                        like "dev" or "prod". Defaults to "pipeline_config".
        
        Returns:
            PipelineConfig: Loaded and validated pipeline configuration with all
                           required and optional parameters populated.
        
        Raises:
            ValueError: If config_name is empty or invalid
            FileNotFoundError: If no configuration file is found
            yaml.YAMLError: If YAML file is malformed
            KeyError: If required fields are missing from YAML
            TypeError: If field types are incorrect
        
        Example:
            >>> config_manager = ConfigurationManager()
            >>> # Load default configuration
            >>> config = config_manager.load_pipeline_config()
            >>> # Load environment-specific configuration
            >>> dev_config = config_manager.load_pipeline_config("dev")
            >>> prod_config = config_manager.load_pipeline_config("prod")
        """
        # Validate config_name parameter
        if not config_name or not config_name.strip():
            raise ValueError("config_name cannot be empty")
        
        config_name = config_name.strip()
        
        # Remove .yaml extension if provided
        if config_name.endswith('.yaml'):
            config_name = config_name[:-5]
        
        # Try multiple file path patterns
        possible_paths = [
            self.config_dir / f"{config_name}.yaml",  # Exact match
            self.config_dir / f"pipeline_config.{config_name}.yaml",  # Environment-specific
            self.config_dir / "pipeline_config.yaml"  # Default fallback
        ]
        
        # Find first existing file
        config_path = None
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
        
        # If no file found, raise error with helpful message
        if config_path is None:
            error_msg = (
                f"Pipeline configuration file not found. Searched for:\n"
                + "\n".join(f"  - {p}" for p in possible_paths)
                + "\n\nPlease create a pipeline configuration file with required settings."
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        logger.info(f"Loading pipeline configuration from {config_path}")
        
        # Read and parse YAML file
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            logger.debug(f"Successfully parsed YAML from {config_path}")
            
        except yaml.YAMLError as e:
            error_msg = f"Failed to parse YAML file {config_path}: {e}"
            logger.error(error_msg)
            raise yaml.YAMLError(error_msg) from e
        
        except IOError as e:
            error_msg = f"Failed to read file {config_path}: {e}"
            logger.error(error_msg)
            raise IOError(error_msg) from e
        
        # Validate that yaml_data is a dictionary
        if not isinstance(yaml_data, dict):
            raise TypeError(
                f"YAML file must contain a dictionary, got {type(yaml_data).__name__}"
            )
        
        # Extract configuration sections with defaults
        try:
            # AWS section (required)
            aws_section = yaml_data.get('aws', {})
            if not aws_section:
                raise KeyError("'aws' section is required in pipeline configuration")
            
            aws_region = aws_section.get('region')
            bedrock_model_id = aws_section.get('bedrock_model_id')
            sagemaker_role_arn = aws_section.get('sagemaker_role_arn')
            s3_bucket = aws_section.get('s3_bucket')
            
            # Validate required AWS fields
            if not aws_region:
                raise KeyError("'aws.region' is required")
            if not bedrock_model_id:
                raise KeyError("'aws.bedrock_model_id' is required")
            if not sagemaker_role_arn:
                raise KeyError("'aws.sagemaker_role_arn' is required")
            if not s3_bucket:
                raise KeyError("'aws.s3_bucket' is required")
            
            # Training section (required)
            training_section = yaml_data.get('training', {})
            if not training_section:
                raise KeyError("'training' section is required in pipeline configuration")
            
            training_instance_type = training_section.get('instance_type')
            if not training_instance_type:
                raise KeyError("'training.instance_type' is required")
            
            # Optional training fields with defaults
            base_model = training_section.get('base_model', 'meta-llama/Llama-3.2-3B')
            max_training_time_seconds = training_section.get('max_training_time_seconds', 86400)
            
            # Inference section (required)
            inference_section = yaml_data.get('inference', {})
            if not inference_section:
                raise KeyError("'inference' section is required in pipeline configuration")
            
            inference_instance_type = inference_section.get('instance_type')
            baseline_model_endpoint = inference_section.get('baseline_model_endpoint')
            
            if not inference_instance_type:
                raise KeyError("'inference.instance_type' is required")
            if not baseline_model_endpoint:
                raise KeyError("'inference.baseline_model_endpoint' is required")
            
            # Pipeline section (required)
            pipeline_section = yaml_data.get('pipeline', {})
            if not pipeline_section:
                raise KeyError("'pipeline' section is required in pipeline configuration")
            
            performance_threshold = pipeline_section.get('performance_threshold')
            max_iterations = pipeline_section.get('max_iterations')
            cleanup_resources = pipeline_section.get('cleanup_resources')
            
            if performance_threshold is None:
                raise KeyError("'pipeline.performance_threshold' is required")
            if max_iterations is None:
                raise KeyError("'pipeline.max_iterations' is required")
            if cleanup_resources is None:
                raise KeyError("'pipeline.cleanup_resources' is required")
            
            # Optional pipeline fields with defaults
            artifact_retention_days = pipeline_section.get('artifact_retention_days', 7)
            
            # Retry section (optional with defaults)
            retry_section = yaml_data.get('retry', {})
            max_retries = retry_section.get('max_attempts', 3)
            initial_backoff_seconds = retry_section.get('initial_backoff_seconds', 2)
            max_backoff_seconds = retry_section.get('max_backoff_seconds', 60)
            
            # Create PipelineConfig instance (validation happens in __post_init__)
            pipeline_config = PipelineConfig(
                aws_region=aws_region,
                bedrock_model_id=bedrock_model_id,
                sagemaker_role_arn=sagemaker_role_arn,
                training_instance_type=training_instance_type,
                inference_instance_type=inference_instance_type,
                baseline_model_endpoint=baseline_model_endpoint,
                performance_threshold=float(performance_threshold),
                max_iterations=int(max_iterations),
                cleanup_resources=bool(cleanup_resources),
                s3_bucket=s3_bucket,
                base_model=base_model,
                max_training_time_seconds=int(max_training_time_seconds),
                max_retries=int(max_retries),
                initial_backoff_seconds=int(initial_backoff_seconds),
                max_backoff_seconds=int(max_backoff_seconds),
                artifact_retention_days=int(artifact_retention_days)
            )
            
            logger.info(
                f"Successfully loaded pipeline configuration from {config_path.name} "
                f"(region: {pipeline_config.aws_region}, "
                f"threshold: {pipeline_config.performance_threshold}, "
                f"max_iterations: {pipeline_config.max_iterations})"
            )
            
            return pipeline_config
            
        except KeyError as e:
            error_msg = (
                f"Missing required field in pipeline configuration: {e}. "
                f"Please ensure all required fields are present in {config_path}"
            )
            logger.error(error_msg)
            raise KeyError(error_msg) from e
        
        except (ValueError, TypeError) as e:
            # Re-raise validation errors from PipelineConfig.__post_init__
            error_msg = f"Invalid pipeline configuration in {config_path}: {e}"
            logger.error(error_msg)
            raise type(e)(error_msg) from e
    
    def validate_config(self, config: Union[UseCase, PipelineConfig]) -> ValidationResult:
        """
        Validate configuration object for completeness and correctness.
        
        Performs comprehensive validation of UseCase or PipelineConfig objects,
        checking for missing required fields, invalid values, and potential issues.
        Returns a ValidationResult with detailed error and warning messages.
        
        Validation checks include:
        - Required field presence and non-empty values
        - Value ranges and formats (e.g., thresholds between 0-1)
        - AWS resource naming conventions
        - Logical consistency (e.g., max_iterations >= 1)
        - Best practice recommendations (warnings)
        
        Args:
            config: Configuration object to validate (UseCase or PipelineConfig)
        
        Returns:
            ValidationResult: Object containing validation status, errors, and warnings
        
        Raises:
            TypeError: If config is not a UseCase or PipelineConfig instance
        
        Example:
            >>> config_manager = ConfigurationManager()
            >>> use_case = UseCase(name="test", description="Test", ...)
            >>> result = config_manager.validate_config(use_case)
            >>> if not result.is_valid:
            ...     print(f"Errors: {result.errors}")
            >>> if result.warnings:
            ...     print(f"Warnings: {result.warnings}")
        """
        # Validate config parameter type
        if not isinstance(config, (UseCase, PipelineConfig)):
            raise TypeError(
                f"config must be UseCase or PipelineConfig, got {type(config).__name__}"
            )
        
        # Create validation result (starts as valid)
        result = ValidationResult(is_valid=True)
        
        # Dispatch to appropriate validation method
        if isinstance(config, UseCase):
            self._validate_use_case(config, result)
        else:  # PipelineConfig
            self._validate_pipeline_config(config, result)
        
        logger.info(
            f"Validation completed for {type(config).__name__}: "
            f"{'valid' if result.is_valid else 'invalid'} "
            f"({len(result.errors)} errors, {len(result.warnings)} warnings)"
        )
        
        return result
    
    def _validate_use_case(self, use_case: UseCase, result: ValidationResult) -> None:
        """
        Validate UseCase configuration.
        
        Args:
            use_case: UseCase object to validate
            result: ValidationResult to populate with errors/warnings
        """
        # Validate name
        if not use_case.name or not use_case.name.strip():
            result.add_error("Use case name is required and cannot be empty")
        elif len(use_case.name.strip()) < 3:
            result.add_warning(
                "Use case name is very short (< 3 characters). "
                "Consider using a more descriptive name."
            )
        elif len(use_case.name) > 100:
            result.add_error("Use case name is too long (> 100 characters)")
        
        # Validate description
        if not use_case.description or not use_case.description.strip():
            result.add_error("Use case description is required and cannot be empty")
        elif len(use_case.description.strip()) < 10:
            result.add_warning(
                "Use case description is very short (< 10 characters). "
                "Consider providing more detail about the use case."
            )
        
        # Validate test_questions
        if not use_case.test_questions:
            result.add_error("Use case must have at least one test question")
        else:
            # Check for empty questions
            empty_questions = [
                i for i, q in enumerate(use_case.test_questions)
                if not q or not q.strip()
            ]
            if empty_questions:
                result.add_error(
                    f"Test questions at indices {empty_questions} are empty"
                )
            
            # Check question count
            if len(use_case.test_questions) < 3:
                result.add_warning(
                    f"Only {len(use_case.test_questions)} test question(s) provided. "
                    "Consider adding more questions (recommended: 5-10) for better evaluation."
                )
            elif len(use_case.test_questions) > 50:
                result.add_warning(
                    f"{len(use_case.test_questions)} test questions provided. "
                    "Large question sets may increase evaluation time and cost."
                )
            
            # Check for duplicate questions
            unique_questions = set(q.strip().lower() for q in use_case.test_questions if q)
            if len(unique_questions) < len(use_case.test_questions):
                result.add_warning(
                    "Duplicate test questions detected. "
                    "Consider using unique questions for better coverage."
                )
            
            # Check question length
            for i, question in enumerate(use_case.test_questions):
                if question and len(question) > 500:
                    result.add_warning(
                        f"Test question {i+1} is very long (> 500 characters). "
                        "Consider breaking it into multiple questions."
                    )
        
        # Validate judge_criteria
        if not use_case.judge_criteria or not use_case.judge_criteria.strip():
            result.add_error("Judge criteria is required and cannot be empty")
        elif len(use_case.judge_criteria.strip()) < 20:
            result.add_warning(
                "Judge criteria is very short (< 20 characters). "
                "Consider providing more detailed evaluation criteria."
            )
        
        # Validate data_generation_prompt
        if not use_case.data_generation_prompt or not use_case.data_generation_prompt.strip():
            result.add_error("Data generation prompt is required and cannot be empty")
        elif len(use_case.data_generation_prompt.strip()) < 20:
            result.add_warning(
                "Data generation prompt is very short (< 20 characters). "
                "Consider providing more detailed instructions for data generation."
            )
        
        # Validate judge_prompt
        if not use_case.judge_prompt or not use_case.judge_prompt.strip():
            result.add_error("Judge prompt is required and cannot be empty")
        elif len(use_case.judge_prompt.strip()) < 20:
            result.add_warning(
                "Judge prompt is very short (< 20 characters). "
                "Consider providing more detailed judging instructions."
            )
        
        # Validate version
        if use_case.version < 1:
            result.add_error("Version must be >= 1")
        elif use_case.version > 1000:
            result.add_warning(
                f"Version number is very high ({use_case.version}). "
                "This may indicate an issue with version tracking."
            )
        
        # Validate created_at
        if use_case.created_at is None:
            result.add_error("created_at timestamp is required")
        elif use_case.created_at > datetime.now():
            result.add_warning(
                "created_at timestamp is in the future. "
                "This may indicate a clock synchronization issue."
            )
    
    def _validate_pipeline_config(self, config: PipelineConfig, result: ValidationResult) -> None:
        """
        Validate PipelineConfig configuration.
        
        Args:
            config: PipelineConfig object to validate
            result: ValidationResult to populate with errors/warnings
        """
        # Validate AWS region
        if not config.aws_region or not config.aws_region.strip():
            result.add_error("AWS region is required and cannot be empty")
        else:
            # Check for valid AWS region format
            valid_regions = [
                'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
                'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1',
                'ap-northeast-1', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
                'ap-south-1', 'sa-east-1', 'ca-central-1'
            ]
            if config.aws_region not in valid_regions:
                result.add_warning(
                    f"AWS region '{config.aws_region}' is not in the common regions list. "
                    "Verify this is a valid AWS region."
                )
        
        # Validate Bedrock model ID
        if not config.bedrock_model_id or not config.bedrock_model_id.strip():
            result.add_error("Bedrock model ID is required and cannot be empty")
        elif not config.bedrock_model_id.startswith('anthropic.claude'):
            result.add_warning(
                f"Bedrock model ID '{config.bedrock_model_id}' does not appear to be a Claude model. "
                "The pipeline is designed for Claude Sonnet 4."
            )
        
        # Validate SageMaker role ARN
        if not config.sagemaker_role_arn or not config.sagemaker_role_arn.strip():
            result.add_error("SageMaker role ARN is required and cannot be empty")
        elif not config.sagemaker_role_arn.startswith('arn:aws:iam::'):
            result.add_error(
                "SageMaker role ARN must start with 'arn:aws:iam::'. "
                f"Got: {config.sagemaker_role_arn}"
            )
        elif not ':role/' in config.sagemaker_role_arn:
            result.add_error(
                "SageMaker role ARN must contain ':role/'. "
                f"Got: {config.sagemaker_role_arn}"
            )
        
        # Validate S3 bucket
        if not config.s3_bucket or not config.s3_bucket.strip():
            result.add_error("S3 bucket name is required and cannot be empty")
        else:
            # Check S3 bucket naming rules
            bucket = config.s3_bucket.strip()
            if len(bucket) < 3 or len(bucket) > 63:
                result.add_error(
                    f"S3 bucket name must be between 3 and 63 characters. "
                    f"Got: {len(bucket)} characters"
                )
            if not bucket[0].isalnum() or not bucket[-1].isalnum():
                result.add_error(
                    "S3 bucket name must start and end with a letter or number"
                )
            if '..' in bucket or '.-' in bucket or '-.' in bucket:
                result.add_error(
                    "S3 bucket name cannot contain consecutive periods or period-dash combinations"
                )
            # Check for uppercase letters (S3 buckets must be lowercase)
            if any(c.isupper() for c in bucket):
                result.add_error(
                    "S3 bucket name must be lowercase"
                )
        
        # Validate training instance type
        if not config.training_instance_type or not config.training_instance_type.strip():
            result.add_error("Training instance type is required and cannot be empty")
        elif not config.training_instance_type.startswith('ml.'):
            result.add_error(
                "Training instance type must start with 'ml.'. "
                f"Got: {config.training_instance_type}"
            )
        elif 'g5' not in config.training_instance_type and 'p3' not in config.training_instance_type:
            result.add_warning(
                f"Training instance type '{config.training_instance_type}' may not have GPU support. "
                "Consider using g5 or p3 instances for model training."
            )
        
        # Validate inference instance type
        if not config.inference_instance_type or not config.inference_instance_type.strip():
            result.add_error("Inference instance type is required and cannot be empty")
        elif not config.inference_instance_type.startswith('ml.'):
            result.add_error(
                "Inference instance type must start with 'ml.'. "
                f"Got: {config.inference_instance_type}"
            )
        
        # Validate baseline model endpoint
        if not config.baseline_model_endpoint or not config.baseline_model_endpoint.strip():
            result.add_error("Baseline model endpoint is required and cannot be empty")
        elif len(config.baseline_model_endpoint) > 63:
            result.add_error(
                "Baseline model endpoint name is too long (> 63 characters)"
            )
        
        # Validate performance threshold
        if config.performance_threshold < 0.0 or config.performance_threshold > 1.0:
            result.add_error(
                f"Performance threshold must be between 0.0 and 1.0. "
                f"Got: {config.performance_threshold}"
            )
        elif config.performance_threshold < 0.5:
            result.add_warning(
                f"Performance threshold is low ({config.performance_threshold}). "
                "Consider setting it to at least 0.5 (50% win rate) for meaningful improvement."
            )
        elif config.performance_threshold > 0.9:
            result.add_warning(
                f"Performance threshold is very high ({config.performance_threshold}). "
                "This may be difficult to achieve and could lead to many iterations."
            )
        
        # Validate max iterations
        if config.max_iterations < 1:
            result.add_error("Max iterations must be >= 1")
        elif config.max_iterations > 10:
            result.add_warning(
                f"Max iterations is high ({config.max_iterations}). "
                "This may result in long execution times and high costs."
            )
        
        # Validate base model
        if not config.base_model or not config.base_model.strip():
            result.add_error("Base model is required and cannot be empty")
        elif 'llama' not in config.base_model.lower():
            result.add_warning(
                f"Base model '{config.base_model}' does not appear to be a Llama model. "
                "The pipeline is designed for Llama 3.2 3B."
            )
        
        # Validate max training time
        if config.max_training_time_seconds < 1:
            result.add_error("Max training time must be >= 1 second")
        elif config.max_training_time_seconds < 300:  # 5 minutes
            result.add_warning(
                f"Max training time is very short ({config.max_training_time_seconds} seconds). "
                "Training may not complete successfully."
            )
        elif config.max_training_time_seconds > 86400:  # 24 hours
            result.add_warning(
                f"Max training time is very long ({config.max_training_time_seconds} seconds). "
                "Consider reducing to avoid excessive costs."
            )
        
        # Validate retry settings
        if config.max_retries < 0:
            result.add_error("Max retries must be >= 0")
        elif config.max_retries > 10:
            result.add_warning(
                f"Max retries is high ({config.max_retries}). "
                "This may mask underlying issues."
            )
        
        if config.initial_backoff_seconds < 1:
            result.add_error("Initial backoff must be >= 1 second")
        elif config.initial_backoff_seconds > 60:
            result.add_warning(
                f"Initial backoff is long ({config.initial_backoff_seconds} seconds). "
                "This may slow down retry attempts unnecessarily."
            )
        
        if config.max_backoff_seconds < config.initial_backoff_seconds:
            result.add_error(
                "Max backoff must be >= initial backoff. "
                f"Got: max={config.max_backoff_seconds}, initial={config.initial_backoff_seconds}"
            )
        elif config.max_backoff_seconds > 300:  # 5 minutes
            result.add_warning(
                f"Max backoff is very long ({config.max_backoff_seconds} seconds). "
                "This may cause long delays during retries."
            )
        
        # Validate artifact retention
        if config.artifact_retention_days < 0:
            result.add_error("Artifact retention days must be >= 0")
        elif config.artifact_retention_days == 0 and not config.cleanup_resources:
            result.add_warning(
                "Artifact retention is 0 days but cleanup_resources is False. "
                "Artifacts will be retained indefinitely, which may incur storage costs."
            )
        elif config.artifact_retention_days > 365:
            result.add_warning(
                f"Artifact retention is very long ({config.artifact_retention_days} days). "
                "This may incur significant storage costs."
            )
        
        # Validate cleanup_resources setting
        if not config.cleanup_resources:
            result.add_warning(
                "Resource cleanup is disabled. "
                "Remember to manually delete endpoints and artifacts to avoid ongoing costs."
            )
