"""
Progress Tracker Component for Automated LLM Finetuning Pipeline

This module provides functionality for tracking pipeline progress, recording
iteration results, persisting pipeline state for resumption, and generating
performance reports.

The ProgressTracker enables:
- Recording iteration results with all relevant metrics
- Retrieving performance history for analysis
- Saving and loading pipeline state for interruption recovery
- Generating summary reports of performance progression
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from dataclasses import asdict

from src.config_models import (
    IterationResult,
    PipelineState,
    PerformanceReport,
    Prompts
)

logger = logging.getLogger(__name__)


# State format versions
STATE_VERSION_CURRENT = 1
REPORT_VERSION_CURRENT = 1
ITERATION_VERSION_CURRENT = 1


class ProgressTracker:
    """
    Tracks pipeline progress and manages state persistence.
    
    The ProgressTracker is responsible for:
    - Recording iteration results to disk
    - Retrieving performance history for use cases
    - Saving pipeline state for resumption after interruption
    - Loading saved pipeline state
    - Generating summary reports of performance across iterations
    
    All data is stored in JSON format with atomic writes to ensure
    data integrity even if the process is interrupted.
    """
    
    def __init__(self, storage_dir: str = "progress/"):
        """
        Initialize ProgressTracker with storage directory.
        
        Args:
            storage_dir: Directory path for storing progress data.
                        Will be created if it doesn't exist.
        
        The storage directory structure:
            progress/
            ├── {use_case_name}/
            │   ├── iteration_1_results.json
            │   ├── iteration_2_results.json
            │   └── ...
            ├── states/
            │   ├── {state_id}.json
            │   └── ...
            └── reports/
                ├── {use_case_name}_report.json
                └── ...
        """
        self.storage_dir = Path(storage_dir)
        self.states_dir = self.storage_dir / "states"
        self.reports_dir = self.storage_dir / "reports"
        
        # Create directory structure
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.states_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ProgressTracker initialized with storage directory: {self.storage_dir}")
    
    def _atomic_write_json(
        self,
        file_path: Path,
        data: Dict[str, Any],
        description: str = "data"
    ) -> None:
        """
        Write JSON data to file with atomic operation.
        
        This method ensures data integrity by:
        1. Writing to a temporary file first
        2. Atomically renaming the temp file to the target file
        3. Cleaning up the temp file if any error occurs
        
        Args:
            file_path: Target file path
            data: Dictionary to serialize as JSON
            description: Description of data being written (for logging)
            
        Raises:
            IOError: If unable to write to disk
        """
        temp_path = file_path.with_suffix('.json.tmp')
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file with proper formatting
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            
            # Atomic rename - this is atomic on POSIX systems and Windows
            temp_path.replace(file_path)
            
            logger.debug(f"Successfully wrote {description} to {file_path}")
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file {temp_path}: {cleanup_error}")
            
            logger.error(f"Failed to write {description} to {file_path}: {e}")
            raise IOError(f"Failed to write {description}: {e}") from e
    
    def _atomic_read_json(
        self,
        file_path: Path,
        description: str = "data"
    ) -> Dict[str, Any]:
        """
        Read JSON data from file with validation.
        
        Args:
            file_path: File path to read from
            description: Description of data being read (for logging)
            
        Returns:
            Dictionary containing the parsed JSON data
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file contains invalid JSON
        """
        if not file_path.exists():
            raise FileNotFoundError(f"{description.capitalize()} file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.debug(f"Successfully read {description} from {file_path}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {description} file {file_path}: {e}")
            raise ValueError(f"Corrupted {description} file: {file_path}") from e
        except Exception as e:
            logger.error(f"Failed to read {description} from {file_path}: {e}")
            raise
    
    def record_iteration(
        self,
        use_case_name: str,
        iteration: int,
        result: IterationResult
    ) -> None:
        """
        Record iteration results to disk.
        
        Args:
            use_case_name: Name of the use case
            iteration: Iteration number (1-indexed)
            result: IterationResult containing all iteration data
        
        Raises:
            ValueError: If use_case_name is empty or iteration < 1
            IOError: If unable to write to disk
        
        The iteration results are stored in JSON format with atomic writes
        to ensure data integrity.
        """
        if not use_case_name or not use_case_name.strip():
            raise ValueError("Use case name cannot be empty")
        if iteration < 1:
            raise ValueError("Iteration must be >= 1")
        
        # Create use case directory if it doesn't exist
        use_case_dir = self.storage_dir / use_case_name
        use_case_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare file path
        file_path = use_case_dir / f"iteration_{iteration}_results.json"
        
        # Convert result to dictionary
        result_dict = self._iteration_result_to_dict(result)
        
        # Write with atomic operation
        self._atomic_write_json(
            file_path,
            result_dict,
            f"iteration {iteration} results for use case '{use_case_name}'"
        )
        
        logger.info(f"Recorded iteration {iteration} results for use case '{use_case_name}'")
    
    def get_performance_history(self, use_case_name: str) -> List[IterationResult]:
        """
        Retrieve all iteration results for a use case.
        
        Args:
            use_case_name: Name of the use case
        
        Returns:
            List of IterationResult objects in chronological order (by iteration number)
        
        Raises:
            ValueError: If use_case_name is empty
            FileNotFoundError: If no results exist for the use case
        
        The results are returned in chronological order based on iteration number.
        """
        if not use_case_name or not use_case_name.strip():
            raise ValueError("Use case name cannot be empty")
        
        use_case_dir = self.storage_dir / use_case_name
        
        if not use_case_dir.exists():
            raise FileNotFoundError(f"No results found for use case '{use_case_name}'")
        
        # Find all iteration result files
        result_files = sorted(use_case_dir.glob("iteration_*_results.json"))
        
        if not result_files:
            raise FileNotFoundError(f"No iteration results found for use case '{use_case_name}'")
        
        # Load and parse all results
        results = []
        for file_path in result_files:
            try:
                result_dict = self._atomic_read_json(
                    file_path,
                    f"iteration result from {file_path.name}"
                )
                result = self._dict_to_iteration_result(result_dict)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to load iteration result from {file_path}: {e}")
                continue
        
        # Sort by iteration number to ensure chronological order
        results.sort(key=lambda r: r.iteration)
        
        logger.info(f"Retrieved {len(results)} iteration results for use case '{use_case_name}'")
        return results
    
    def save_pipeline_state(
        self,
        use_case_name: str,
        state: PipelineState
    ) -> str:
        """
        Save pipeline state for resumption.
        
        Args:
            use_case_name: Name of the use case
            state: PipelineState containing current execution state
        
        Returns:
            State ID (unique identifier for this saved state)
        
        Raises:
            ValueError: If use_case_name is empty
            IOError: If unable to write to disk
        
        The state is saved with a unique ID based on timestamp and use case name.
        This allows multiple saved states for the same use case.
        """
        if not use_case_name or not use_case_name.strip():
            raise ValueError("Use case name cannot be empty")
        
        # Generate unique state ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        state_id = f"{use_case_name}_{timestamp}"
        
        # Prepare file path
        file_path = self.states_dir / f"{state_id}.json"
        
        # Convert state to dictionary
        state_dict = self._pipeline_state_to_dict(state)
        state_dict['state_id'] = state_id
        
        # Write with atomic operation
        self._atomic_write_json(
            file_path,
            state_dict,
            f"pipeline state {state_id}"
        )
        
        logger.info(f"Saved pipeline state with ID: {state_id}")
        return state_id
    
    def load_pipeline_state(self, state_id: str) -> PipelineState:
        """
        Load saved pipeline state.
        
        Args:
            state_id: Unique identifier of the saved state
        
        Returns:
            PipelineState object with restored state
        
        Raises:
            ValueError: If state_id is empty
            FileNotFoundError: If state file doesn't exist
            ValueError: If state data is invalid or corrupted
        
        The loaded state can be used to resume pipeline execution from
        the point of interruption.
        """
        if not state_id or not state_id.strip():
            raise ValueError("State ID cannot be empty")
        
        file_path = self.states_dir / f"{state_id}.json"
        
        if not file_path.exists():
            raise FileNotFoundError(f"State file not found: {state_id}")
        
        # Read with validation
        state_dict = self._atomic_read_json(file_path, f"pipeline state {state_id}")
        
        # Validate data integrity
        self._validate_state_data(state_dict)
        
        # Convert to PipelineState object
        state = self._dict_to_pipeline_state(state_dict)
        
        logger.info(f"Loaded pipeline state: {state_id}")
        return state
    
    def generate_summary_report(self, use_case_name: str) -> PerformanceReport:
        """
        Generate summary report of performance progression.
        
        Args:
            use_case_name: Name of the use case
        
        Returns:
            PerformanceReport with summary statistics and iteration history
        
        Raises:
            ValueError: If use_case_name is empty
            FileNotFoundError: If no results exist for the use case
        
        The report includes:
        - Total number of iterations
        - Initial and final win rates
        - Overall improvement
        - Best performing iteration
        - Complete iteration history
        """
        if not use_case_name or not use_case_name.strip():
            raise ValueError("Use case name cannot be empty")
        
        # Get all iteration results
        iteration_history = self.get_performance_history(use_case_name)
        
        if not iteration_history:
            raise FileNotFoundError(f"No iteration results found for use case '{use_case_name}'")
        
        # Calculate summary statistics
        total_iterations = len(iteration_history)
        initial_win_rate = iteration_history[0].win_rate
        final_win_rate = iteration_history[-1].win_rate
        improvement = final_win_rate - initial_win_rate
        
        # Find best iteration
        best_iteration = max(iteration_history, key=lambda r: r.win_rate).iteration
        
        # Create report
        report = PerformanceReport(
            use_case_name=use_case_name,
            total_iterations=total_iterations,
            initial_win_rate=initial_win_rate,
            final_win_rate=final_win_rate,
            improvement=improvement,
            best_iteration=best_iteration,
            iteration_history=iteration_history
        )
        
        # Save report to disk
        self._save_report(report)
        
        logger.info(f"Generated summary report for use case '{use_case_name}': "
                   f"{total_iterations} iterations, improvement: {improvement:+.2%}")
        
        return report
    
    def _save_report(self, report: PerformanceReport) -> None:
        """
        Save performance report to disk with atomic write.
        
        Args:
            report: PerformanceReport to save
        """
        file_path = self.reports_dir / f"{report.use_case_name}_report.json"
        report_dict = self._performance_report_to_dict(report)
        
        try:
            self._atomic_write_json(
                file_path,
                report_dict,
                f"performance report for '{report.use_case_name}'"
            )
        except Exception as e:
            logger.warning(f"Failed to save performance report: {e}")
    
    # Serialization helper methods
    
    def _iteration_result_to_dict(self, result: IterationResult) -> Dict[str, Any]:
        """
        Convert IterationResult to dictionary for JSON serialization.
        
        Args:
            result: IterationResult object to serialize
            
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'version': ITERATION_VERSION_CURRENT,
            'iteration': result.iteration,
            'win_rate': result.win_rate,
            'prompts_used': {
                'data_generation_prompt': result.prompts_used.data_generation_prompt,
                'judge_prompt': result.prompts_used.judge_prompt
            },
            'training_time_seconds': result.training_time_seconds,
            'evaluation_time': result.evaluation_time.isoformat(),
            'model_artifact_uri': result.model_artifact_uri,
            'endpoint_name': result.endpoint_name
        }
    
    def _dict_to_iteration_result(self, data: Dict[str, Any]) -> IterationResult:
        """
        Convert dictionary to IterationResult object.
        
        Args:
            data: Dictionary containing iteration result data
            
        Returns:
            IterationResult object
            
        Raises:
            KeyError: If required fields are missing
            ValueError: If data values are invalid
        """
        # Migrate data if needed
        data = self._migrate_iteration_data(data)
        
        # Validate data integrity
        self._validate_iteration_data(data)
        
        return IterationResult(
            iteration=data['iteration'],
            win_rate=data['win_rate'],
            prompts_used=Prompts(
                data_generation_prompt=data['prompts_used']['data_generation_prompt'],
                judge_prompt=data['prompts_used']['judge_prompt']
            ),
            training_time_seconds=data['training_time_seconds'],
            evaluation_time=datetime.fromisoformat(data['evaluation_time']),
            model_artifact_uri=data['model_artifact_uri'],
            endpoint_name=data['endpoint_name']
        )
    
    def _pipeline_state_to_dict(self, state: PipelineState) -> Dict[str, Any]:
        """
        Convert PipelineState to dictionary for JSON serialization.
        
        Args:
            state: PipelineState object to serialize
            
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'version': STATE_VERSION_CURRENT,
            'use_case_name': state.use_case_name,
            'current_iteration': state.current_iteration,
            'completed_steps': state.completed_steps,
            'intermediate_results': state.intermediate_results,
            'timestamp': state.timestamp.isoformat()
        }
    
    def _dict_to_pipeline_state(self, data: Dict[str, Any]) -> PipelineState:
        """
        Convert dictionary to PipelineState object.
        
        Args:
            data: Dictionary containing pipeline state data
            
        Returns:
            PipelineState object
            
        Raises:
            KeyError: If required fields are missing
            ValueError: If data values are invalid
        """
        # Migrate data if needed
        data = self._migrate_state_data(data)
        
        return PipelineState(
            use_case_name=data['use_case_name'],
            current_iteration=data['current_iteration'],
            completed_steps=data['completed_steps'],
            intermediate_results=data['intermediate_results'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )
    
    def _performance_report_to_dict(self, report: PerformanceReport) -> Dict[str, Any]:
        """
        Convert PerformanceReport to dictionary for JSON serialization.
        
        Args:
            report: PerformanceReport object to serialize
            
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'version': REPORT_VERSION_CURRENT,
            'use_case_name': report.use_case_name,
            'total_iterations': report.total_iterations,
            'initial_win_rate': report.initial_win_rate,
            'final_win_rate': report.final_win_rate,
            'improvement': report.improvement,
            'best_iteration': report.best_iteration,
            'iteration_history': [
                self._iteration_result_to_dict(result)
                for result in report.iteration_history
            ]
        }
    
    def _dict_to_performance_report(self, data: Dict[str, Any]) -> PerformanceReport:
        """
        Convert dictionary to PerformanceReport object.
        
        Args:
            data: Dictionary containing performance report data
            
        Returns:
            PerformanceReport object
            
        Raises:
            KeyError: If required fields are missing
            ValueError: If data values are invalid
        """
        # Migrate data if needed
        data = self._migrate_report_data(data)
        
        # Validate data integrity
        self._validate_report_data(data)
        
        return PerformanceReport(
            use_case_name=data['use_case_name'],
            total_iterations=data['total_iterations'],
            initial_win_rate=data['initial_win_rate'],
            final_win_rate=data['final_win_rate'],
            improvement=data['improvement'],
            best_iteration=data['best_iteration'],
            iteration_history=[
                self._dict_to_iteration_result(result_dict)
                for result_dict in data['iteration_history']
            ]
        )
    
    def _validate_state_data(self, data: Dict[str, Any]) -> None:
        """
        Validate state data integrity.
        
        Args:
            data: State data dictionary to validate
        
        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = [
            'use_case_name',
            'current_iteration',
            'completed_steps',
            'intermediate_results',
            'timestamp'
        ]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field in state data: {field}")
        
        if not isinstance(data['completed_steps'], list):
            raise ValueError("completed_steps must be a list")
        
        if not isinstance(data['intermediate_results'], dict):
            raise ValueError("intermediate_results must be a dictionary")
        
        if data['current_iteration'] < 0:
            raise ValueError("current_iteration must be >= 0")
        
        # Validate use_case_name is non-empty
        if not data['use_case_name'] or not data['use_case_name'].strip():
            raise ValueError("use_case_name cannot be empty")
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(data['timestamp'])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid timestamp format: {e}")
    
    def _validate_iteration_data(self, data: Dict[str, Any]) -> None:
        """
        Validate iteration result data integrity.
        
        Args:
            data: Iteration result data dictionary to validate
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = [
            'iteration',
            'win_rate',
            'prompts_used',
            'training_time_seconds',
            'evaluation_time',
            'model_artifact_uri',
            'endpoint_name'
        ]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field in iteration data: {field}")
        
        # Validate iteration number
        if data['iteration'] < 1:
            raise ValueError("iteration must be >= 1")
        
        # Validate win_rate range
        if not (0.0 <= data['win_rate'] <= 1.0):
            raise ValueError("win_rate must be between 0.0 and 1.0")
        
        # Validate training_time_seconds
        if data['training_time_seconds'] < 0:
            raise ValueError("training_time_seconds must be >= 0")
        
        # Validate prompts_used structure
        if not isinstance(data['prompts_used'], dict):
            raise ValueError("prompts_used must be a dictionary")
        
        required_prompt_fields = ['data_generation_prompt', 'judge_prompt']
        for field in required_prompt_fields:
            if field not in data['prompts_used']:
                raise ValueError(f"Missing required field in prompts_used: {field}")
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(data['evaluation_time'])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid evaluation_time format: {e}")
        
        # Validate URIs and names are non-empty
        if not data['model_artifact_uri'] or not data['model_artifact_uri'].strip():
            raise ValueError("model_artifact_uri cannot be empty")
        
        if not data['endpoint_name'] or not data['endpoint_name'].strip():
            raise ValueError("endpoint_name cannot be empty")
    
    def _validate_report_data(self, data: Dict[str, Any]) -> None:
        """
        Validate performance report data integrity.
        
        Args:
            data: Performance report data dictionary to validate
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = [
            'use_case_name',
            'total_iterations',
            'initial_win_rate',
            'final_win_rate',
            'improvement',
            'best_iteration',
            'iteration_history'
        ]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field in report data: {field}")
        
        # Validate use_case_name
        if not data['use_case_name'] or not data['use_case_name'].strip():
            raise ValueError("use_case_name cannot be empty")
        
        # Validate total_iterations
        if data['total_iterations'] < 0:
            raise ValueError("total_iterations must be >= 0")
        
        # Validate win rates
        for field in ['initial_win_rate', 'final_win_rate']:
            if not (0.0 <= data[field] <= 1.0):
                raise ValueError(f"{field} must be between 0.0 and 1.0")
        
        # Validate best_iteration
        if data['best_iteration'] < 1:
            raise ValueError("best_iteration must be >= 1")
        
        # Validate iteration_history is a list
        if not isinstance(data['iteration_history'], list):
            raise ValueError("iteration_history must be a list")
        
        # Validate iteration_history length matches total_iterations
        if len(data['iteration_history']) != data['total_iterations']:
            raise ValueError(
                f"iteration_history length ({len(data['iteration_history'])}) "
                f"does not match total_iterations ({data['total_iterations']})"
            )
        
        # Validate improvement calculation
        expected_improvement = data['final_win_rate'] - data['initial_win_rate']
        if abs(data['improvement'] - expected_improvement) > 0.001:
            raise ValueError(
                f"improvement ({data['improvement']}) does not match "
                f"final_win_rate - initial_win_rate ({expected_improvement})"
            )
        
        # Validate each iteration in history
        for i, iter_data in enumerate(data['iteration_history']):
            try:
                self._validate_iteration_data(iter_data)
            except ValueError as e:
                raise ValueError(f"Invalid iteration data at index {i}: {e}")
    
    def _migrate_state_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate state data from older versions to current version.
        
        Args:
            data: State data dictionary (may be from older version)
            
        Returns:
            Migrated data dictionary compatible with current version
            
        This method handles backward compatibility by migrating data
        from older state format versions to the current version.
        """
        # Get version from data, default to 0 if not present (legacy format)
        version = data.get('version', 0)
        
        if version == STATE_VERSION_CURRENT:
            # Already current version, no migration needed
            return data
        
        logger.info(f"Migrating state data from version {version} to {STATE_VERSION_CURRENT}")
        
        # Migration from version 0 (legacy) to version 1
        if version == 0:
            # Version 0 didn't have a version field
            # Add version field
            data['version'] = 1
            
            # Ensure all required fields exist with defaults if missing
            if 'completed_steps' not in data:
                data['completed_steps'] = []
            if 'intermediate_results' not in data:
                data['intermediate_results'] = {}
            
            logger.debug("Migrated state from version 0 to version 1")
        
        # Future migrations would go here
        # if version == 1:
        #     # Migrate from version 1 to version 2
        #     data['version'] = 2
        #     # ... migration logic ...
        
        return data
    
    def _migrate_iteration_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate iteration result data from older versions to current version.
        
        Args:
            data: Iteration result data dictionary (may be from older version)
            
        Returns:
            Migrated data dictionary compatible with current version
        """
        version = data.get('version', 0)
        
        if version == ITERATION_VERSION_CURRENT:
            return data
        
        logger.info(f"Migrating iteration data from version {version} to {ITERATION_VERSION_CURRENT}")
        
        # Migration from version 0 (legacy) to version 1
        if version == 0:
            data['version'] = 1
            
            # Ensure prompts_used structure exists
            if 'prompts_used' not in data:
                data['prompts_used'] = {
                    'data_generation_prompt': '',
                    'judge_prompt': ''
                }
            
            logger.debug("Migrated iteration data from version 0 to version 1")
        
        return data
    
    def _migrate_report_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate performance report data from older versions to current version.
        
        Args:
            data: Performance report data dictionary (may be from older version)
            
        Returns:
            Migrated data dictionary compatible with current version
        """
        version = data.get('version', 0)
        
        if version == REPORT_VERSION_CURRENT:
            return data
        
        logger.info(f"Migrating report data from version {version} to {REPORT_VERSION_CURRENT}")
        
        # Migration from version 0 (legacy) to version 1
        if version == 0:
            data['version'] = 1
            
            # Migrate each iteration in history
            if 'iteration_history' in data:
                data['iteration_history'] = [
                    self._migrate_iteration_data(iter_data)
                    for iter_data in data['iteration_history']
                ]
            
            logger.debug("Migrated report data from version 0 to version 1")
        
        return data
