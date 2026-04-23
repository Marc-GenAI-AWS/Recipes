"""
Unit Tests for Progress Tracker Persistence Logic

Tests cover:
- JSON serialization and deserialization
- Atomic file writes
- State versioning and migration
- Data integrity validation
- Error handling for corrupted data
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock

from src.progress_tracker import ProgressTracker, STATE_VERSION_CURRENT, ITERATION_VERSION_CURRENT, REPORT_VERSION_CURRENT
from src.config_models import (
    IterationResult,
    PipelineState,
    PerformanceReport,
    Prompts
)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def progress_tracker(temp_storage_dir):
    """Create a ProgressTracker instance with temporary storage."""
    return ProgressTracker(storage_dir=temp_storage_dir)


@pytest.fixture
def sample_prompts():
    """Create sample prompts for testing."""
    return Prompts(
        data_generation_prompt="Generate training data for customer support",
        judge_prompt="Evaluate responses based on helpfulness and clarity"
    )


@pytest.fixture
def sample_iteration_result(sample_prompts):
    """Create a sample iteration result for testing."""
    return IterationResult(
        iteration=1,
        win_rate=0.65,
        prompts_used=sample_prompts,
        training_time_seconds=3600,
        evaluation_time=datetime(2024, 1, 15, 10, 30, 0),
        model_artifact_uri="s3://bucket/model/artifact.tar.gz",
        endpoint_name="test-endpoint-1"
    )


@pytest.fixture
def sample_pipeline_state():
    """Create a sample pipeline state for testing."""
    return PipelineState(
        use_case_name="customer_support",
        current_iteration=2,
        completed_steps=["data_generation", "training", "deployment"],
        intermediate_results={
            "training_job_name": "test-job-123",
            "endpoint_name": "test-endpoint-1"
        },
        timestamp=datetime(2024, 1, 15, 12, 0, 0)
    )


class TestJSONSerialization:
    """Tests for JSON serialization and deserialization."""
    
    def test_iteration_result_serialization_round_trip(
        self,
        progress_tracker,
        sample_iteration_result
    ):
        """Test that iteration result can be serialized and deserialized."""
        # Serialize
        result_dict = progress_tracker._iteration_result_to_dict(sample_iteration_result)
        
        # Verify dictionary structure
        assert result_dict['iteration'] == 1
        assert result_dict['win_rate'] == 0.65
        assert result_dict['version'] == ITERATION_VERSION_CURRENT
        assert 'prompts_used' in result_dict
        
        # Deserialize
        restored_result = progress_tracker._dict_to_iteration_result(result_dict)
        
        # Verify round-trip
        assert restored_result.iteration == sample_iteration_result.iteration
        assert restored_result.win_rate == sample_iteration_result.win_rate
        assert restored_result.training_time_seconds == sample_iteration_result.training_time_seconds
        assert restored_result.model_artifact_uri == sample_iteration_result.model_artifact_uri
        assert restored_result.endpoint_name == sample_iteration_result.endpoint_name
    
    def test_pipeline_state_serialization_round_trip(
        self,
        progress_tracker,
        sample_pipeline_state
    ):
        """Test that pipeline state can be serialized and deserialized."""
        # Serialize
        state_dict = progress_tracker._pipeline_state_to_dict(sample_pipeline_state)
        
        # Verify dictionary structure
        assert state_dict['use_case_name'] == "customer_support"
        assert state_dict['current_iteration'] == 2
        assert state_dict['version'] == STATE_VERSION_CURRENT
        assert len(state_dict['completed_steps']) == 3
        
        # Deserialize
        restored_state = progress_tracker._dict_to_pipeline_state(state_dict)
        
        # Verify round-trip
        assert restored_state.use_case_name == sample_pipeline_state.use_case_name
        assert restored_state.current_iteration == sample_pipeline_state.current_iteration
        assert restored_state.completed_steps == sample_pipeline_state.completed_steps
        assert restored_state.intermediate_results == sample_pipeline_state.intermediate_results
    
    def test_performance_report_serialization_round_trip(
        self,
        progress_tracker,
        sample_prompts
    ):
        """Test that performance report can be serialized and deserialized."""
        # Create sample report
        iteration_results = [
            IterationResult(
                iteration=i,
                win_rate=0.6 + i * 0.05,
                prompts_used=sample_prompts,
                training_time_seconds=3600,
                evaluation_time=datetime(2024, 1, 15, 10, 30, 0),
                model_artifact_uri=f"s3://bucket/model/artifact_{i}.tar.gz",
                endpoint_name=f"test-endpoint-{i}"
            )
            for i in range(1, 4)
        ]
        
        report = PerformanceReport(
            use_case_name="customer_support",
            total_iterations=3,
            initial_win_rate=0.65,
            final_win_rate=0.75,
            improvement=0.10,
            best_iteration=3,
            iteration_history=iteration_results
        )
        
        # Serialize
        report_dict = progress_tracker._performance_report_to_dict(report)
        
        # Verify dictionary structure
        assert report_dict['use_case_name'] == "customer_support"
        assert report_dict['total_iterations'] == 3
        assert report_dict['version'] == REPORT_VERSION_CURRENT
        assert len(report_dict['iteration_history']) == 3
        
        # Deserialize
        restored_report = progress_tracker._dict_to_performance_report(report_dict)
        
        # Verify round-trip
        assert restored_report.use_case_name == report.use_case_name
        assert restored_report.total_iterations == report.total_iterations
        assert restored_report.initial_win_rate == report.initial_win_rate
        assert restored_report.final_win_rate == report.final_win_rate
        assert len(restored_report.iteration_history) == 3


class TestAtomicWrites:
    """Tests for atomic file write operations."""
    
    def test_atomic_write_creates_file(self, progress_tracker, temp_storage_dir):
        """Test that atomic write creates the target file."""
        file_path = Path(temp_storage_dir) / "test.json"
        data = {"key": "value", "number": 42}
        
        progress_tracker._atomic_write_json(file_path, data, "test data")
        
        assert file_path.exists()
        
        # Verify content
        with open(file_path, 'r') as f:
            loaded_data = json.load(f)
        assert loaded_data == data
    
    def test_atomic_write_no_temp_file_left_on_success(
        self,
        progress_tracker,
        temp_storage_dir
    ):
        """Test that temporary file is removed after successful write."""
        file_path = Path(temp_storage_dir) / "test.json"
        temp_path = file_path.with_suffix('.json.tmp')
        data = {"key": "value"}
        
        progress_tracker._atomic_write_json(file_path, data, "test data")
        
        assert file_path.exists()
        assert not temp_path.exists()
    
    def test_atomic_write_cleans_up_temp_on_error(
        self,
        progress_tracker,
        temp_storage_dir
    ):
        """Test that temporary file is cleaned up on write error."""
        file_path = Path(temp_storage_dir) / "test.json"
        temp_path = file_path.with_suffix('.json.tmp')
        
        # Mock the open function to raise an error during write
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with pytest.raises(IOError):
                progress_tracker._atomic_write_json(file_path, {"key": "value"}, "test data")
    
    def test_atomic_write_creates_parent_directories(
        self,
        progress_tracker,
        temp_storage_dir
    ):
        """Test that atomic write creates parent directories if needed."""
        file_path = Path(temp_storage_dir) / "nested" / "dir" / "test.json"
        data = {"key": "value"}
        
        progress_tracker._atomic_write_json(file_path, data, "test data")
        
        assert file_path.exists()
        assert file_path.parent.exists()
    
    def test_atomic_read_loads_valid_json(self, progress_tracker, temp_storage_dir):
        """Test that atomic read loads valid JSON file."""
        file_path = Path(temp_storage_dir) / "test.json"
        data = {"key": "value", "number": 42}
        
        # Write file
        with open(file_path, 'w') as f:
            json.dump(data, f)
        
        # Read file
        loaded_data = progress_tracker._atomic_read_json(file_path, "test data")
        
        assert loaded_data == data
    
    def test_atomic_read_raises_on_missing_file(
        self,
        progress_tracker,
        temp_storage_dir
    ):
        """Test that atomic read raises FileNotFoundError for missing file."""
        file_path = Path(temp_storage_dir) / "nonexistent.json"
        
        with pytest.raises(FileNotFoundError, match="Test data file not found"):
            progress_tracker._atomic_read_json(file_path, "test data")
    
    def test_atomic_read_raises_on_invalid_json(
        self,
        progress_tracker,
        temp_storage_dir
    ):
        """Test that atomic read raises ValueError for invalid JSON."""
        file_path = Path(temp_storage_dir) / "invalid.json"
        
        # Write invalid JSON
        with open(file_path, 'w') as f:
            f.write("{ invalid json }")
        
        with pytest.raises(ValueError, match="Corrupted test data file"):
            progress_tracker._atomic_read_json(file_path, "test data")


class TestStateVersioning:
    """Tests for state versioning and migration."""
    
    def test_current_version_no_migration(self, progress_tracker):
        """Test that current version data requires no migration."""
        data = {
            'version': STATE_VERSION_CURRENT,
            'use_case_name': 'test',
            'current_iteration': 1,
            'completed_steps': [],
            'intermediate_results': {},
            'timestamp': '2024-01-15T10:30:00'
        }
        
        migrated = progress_tracker._migrate_state_data(data)
        
        assert migrated['version'] == STATE_VERSION_CURRENT
        assert migrated == data
    
    def test_legacy_version_0_migration(self, progress_tracker):
        """Test migration from version 0 (legacy) to current version."""
        data = {
            # No version field (legacy format)
            'use_case_name': 'test',
            'current_iteration': 1,
            'completed_steps': ['step1'],
            'intermediate_results': {'key': 'value'},
            'timestamp': '2024-01-15T10:30:00'
        }
        
        migrated = progress_tracker._migrate_state_data(data)
        
        assert migrated['version'] == 1
        assert migrated['use_case_name'] == 'test'
        assert migrated['completed_steps'] == ['step1']
    
    def test_legacy_version_0_adds_missing_fields(self, progress_tracker):
        """Test that migration adds missing fields with defaults."""
        data = {
            'use_case_name': 'test',
            'current_iteration': 1,
            'timestamp': '2024-01-15T10:30:00'
            # Missing completed_steps and intermediate_results
        }
        
        migrated = progress_tracker._migrate_state_data(data)
        
        assert 'completed_steps' in migrated
        assert migrated['completed_steps'] == []
        assert 'intermediate_results' in migrated
        assert migrated['intermediate_results'] == {}
    
    def test_iteration_version_migration(self, progress_tracker):
        """Test migration of iteration result data."""
        data = {
            # No version field (legacy)
            'iteration': 1,
            'win_rate': 0.65,
            'training_time_seconds': 3600,
            'evaluation_time': '2024-01-15T10:30:00',
            'model_artifact_uri': 's3://bucket/model.tar.gz',
            'endpoint_name': 'test-endpoint'
            # Missing prompts_used
        }
        
        migrated = progress_tracker._migrate_iteration_data(data)
        
        assert migrated['version'] == 1
        assert 'prompts_used' in migrated
        assert migrated['prompts_used']['data_generation_prompt'] == ''
        assert migrated['prompts_used']['judge_prompt'] == ''
    
    def test_report_version_migration(self, progress_tracker):
        """Test migration of performance report data."""
        data = {
            # No version field (legacy)
            'use_case_name': 'test',
            'total_iterations': 2,
            'initial_win_rate': 0.6,
            'final_win_rate': 0.7,
            'improvement': 0.1,
            'best_iteration': 2,
            'iteration_history': [
                {
                    'iteration': 1,
                    'win_rate': 0.6,
                    'training_time_seconds': 3600,
                    'evaluation_time': '2024-01-15T10:30:00',
                    'model_artifact_uri': 's3://bucket/model.tar.gz',
                    'endpoint_name': 'test-endpoint'
                }
            ]
        }
        
        migrated = progress_tracker._migrate_report_data(data)
        
        assert migrated['version'] == 1
        # Check that iteration history was also migrated
        assert migrated['iteration_history'][0]['version'] == 1


class TestDataValidation:
    """Tests for data integrity validation."""
    
    def test_validate_state_data_valid(self, progress_tracker):
        """Test validation passes for valid state data."""
        data = {
            'use_case_name': 'test',
            'current_iteration': 1,
            'completed_steps': ['step1', 'step2'],
            'intermediate_results': {'key': 'value'},
            'timestamp': '2024-01-15T10:30:00'
        }
        
        # Should not raise
        progress_tracker._validate_state_data(data)
    
    def test_validate_state_data_missing_field(self, progress_tracker):
        """Test validation fails for missing required field."""
        data = {
            'use_case_name': 'test',
            'current_iteration': 1,
            # Missing completed_steps
            'intermediate_results': {},
            'timestamp': '2024-01-15T10:30:00'
        }
        
        with pytest.raises(ValueError, match="Missing required field.*completed_steps"):
            progress_tracker._validate_state_data(data)
    
    def test_validate_state_data_invalid_iteration(self, progress_tracker):
        """Test validation fails for negative iteration."""
        data = {
            'use_case_name': 'test',
            'current_iteration': -1,
            'completed_steps': [],
            'intermediate_results': {},
            'timestamp': '2024-01-15T10:30:00'
        }
        
        with pytest.raises(ValueError, match="current_iteration must be >= 0"):
            progress_tracker._validate_state_data(data)
    
    def test_validate_state_data_empty_use_case_name(self, progress_tracker):
        """Test validation fails for empty use case name."""
        data = {
            'use_case_name': '   ',
            'current_iteration': 1,
            'completed_steps': [],
            'intermediate_results': {},
            'timestamp': '2024-01-15T10:30:00'
        }
        
        with pytest.raises(ValueError, match="use_case_name cannot be empty"):
            progress_tracker._validate_state_data(data)
    
    def test_validate_iteration_data_valid(self, progress_tracker):
        """Test validation passes for valid iteration data."""
        data = {
            'iteration': 1,
            'win_rate': 0.65,
            'prompts_used': {
                'data_generation_prompt': 'prompt1',
                'judge_prompt': 'prompt2'
            },
            'training_time_seconds': 3600,
            'evaluation_time': '2024-01-15T10:30:00',
            'model_artifact_uri': 's3://bucket/model.tar.gz',
            'endpoint_name': 'test-endpoint'
        }
        
        # Should not raise
        progress_tracker._validate_iteration_data(data)
    
    def test_validate_iteration_data_invalid_win_rate(self, progress_tracker):
        """Test validation fails for win rate out of range."""
        data = {
            'iteration': 1,
            'win_rate': 1.5,  # Invalid: > 1.0
            'prompts_used': {
                'data_generation_prompt': 'prompt1',
                'judge_prompt': 'prompt2'
            },
            'training_time_seconds': 3600,
            'evaluation_time': '2024-01-15T10:30:00',
            'model_artifact_uri': 's3://bucket/model.tar.gz',
            'endpoint_name': 'test-endpoint'
        }
        
        with pytest.raises(ValueError, match="win_rate must be between 0.0 and 1.0"):
            progress_tracker._validate_iteration_data(data)
    
    def test_validate_iteration_data_missing_prompts(self, progress_tracker):
        """Test validation fails for missing prompts_used fields."""
        data = {
            'iteration': 1,
            'win_rate': 0.65,
            'prompts_used': {
                'data_generation_prompt': 'prompt1'
                # Missing judge_prompt
            },
            'training_time_seconds': 3600,
            'evaluation_time': '2024-01-15T10:30:00',
            'model_artifact_uri': 's3://bucket/model.tar.gz',
            'endpoint_name': 'test-endpoint'
        }
        
        with pytest.raises(ValueError, match="Missing required field in prompts_used"):
            progress_tracker._validate_iteration_data(data)
    
    def test_validate_report_data_valid(self, progress_tracker):
        """Test validation passes for valid report data."""
        data = {
            'use_case_name': 'test',
            'total_iterations': 2,
            'initial_win_rate': 0.6,
            'final_win_rate': 0.7,
            'improvement': 0.1,
            'best_iteration': 2,
            'iteration_history': [
                {
                    'iteration': 1,
                    'win_rate': 0.6,
                    'prompts_used': {
                        'data_generation_prompt': 'prompt1',
                        'judge_prompt': 'prompt2'
                    },
                    'training_time_seconds': 3600,
                    'evaluation_time': '2024-01-15T10:30:00',
                    'model_artifact_uri': 's3://bucket/model1.tar.gz',
                    'endpoint_name': 'test-endpoint-1'
                },
                {
                    'iteration': 2,
                    'win_rate': 0.7,
                    'prompts_used': {
                        'data_generation_prompt': 'prompt1',
                        'judge_prompt': 'prompt2'
                    },
                    'training_time_seconds': 3600,
                    'evaluation_time': '2024-01-15T11:30:00',
                    'model_artifact_uri': 's3://bucket/model2.tar.gz',
                    'endpoint_name': 'test-endpoint-2'
                }
            ]
        }
        
        # Should not raise
        progress_tracker._validate_report_data(data)
    
    def test_validate_report_data_mismatched_iterations(self, progress_tracker):
        """Test validation fails when iteration history length doesn't match total."""
        data = {
            'use_case_name': 'test',
            'total_iterations': 3,  # Says 3
            'initial_win_rate': 0.6,
            'final_win_rate': 0.7,
            'improvement': 0.1,
            'best_iteration': 2,
            'iteration_history': [  # But only has 1
                {
                    'iteration': 1,
                    'win_rate': 0.6,
                    'prompts_used': {
                        'data_generation_prompt': 'prompt1',
                        'judge_prompt': 'prompt2'
                    },
                    'training_time_seconds': 3600,
                    'evaluation_time': '2024-01-15T10:30:00',
                    'model_artifact_uri': 's3://bucket/model.tar.gz',
                    'endpoint_name': 'test-endpoint'
                }
            ]
        }
        
        with pytest.raises(ValueError, match="iteration_history length.*does not match total_iterations"):
            progress_tracker._validate_report_data(data)
    
    def test_validate_report_data_incorrect_improvement(self, progress_tracker):
        """Test validation fails when improvement calculation is wrong."""
        data = {
            'use_case_name': 'test',
            'total_iterations': 1,
            'initial_win_rate': 0.6,
            'final_win_rate': 0.7,
            'improvement': 0.5,  # Wrong: should be 0.1
            'best_iteration': 1,
            'iteration_history': [
                {
                    'iteration': 1,
                    'win_rate': 0.7,
                    'prompts_used': {
                        'data_generation_prompt': 'prompt1',
                        'judge_prompt': 'prompt2'
                    },
                    'training_time_seconds': 3600,
                    'evaluation_time': '2024-01-15T10:30:00',
                    'model_artifact_uri': 's3://bucket/model.tar.gz',
                    'endpoint_name': 'test-endpoint'
                }
            ]
        }
        
        with pytest.raises(ValueError, match="improvement.*does not match"):
            progress_tracker._validate_report_data(data)


class TestPersistenceIntegration:
    """Integration tests for complete persistence workflows."""
    
    def test_save_and_load_iteration_result(
        self,
        progress_tracker,
        sample_iteration_result
    ):
        """Test saving and loading iteration result through full workflow."""
        # Save
        progress_tracker.record_iteration(
            "customer_support",
            1,
            sample_iteration_result
        )
        
        # Load
        history = progress_tracker.get_performance_history("customer_support")
        
        assert len(history) == 1
        assert history[0].iteration == 1
        assert history[0].win_rate == 0.65
    
    def test_save_and_load_pipeline_state(
        self,
        progress_tracker,
        sample_pipeline_state
    ):
        """Test saving and loading pipeline state through full workflow."""
        # Save
        state_id = progress_tracker.save_pipeline_state(
            "customer_support",
            sample_pipeline_state
        )
        
        assert state_id is not None
        assert "customer_support" in state_id
        
        # Load
        loaded_state = progress_tracker.load_pipeline_state(state_id)
        
        assert loaded_state.use_case_name == sample_pipeline_state.use_case_name
        assert loaded_state.current_iteration == sample_pipeline_state.current_iteration
        assert loaded_state.completed_steps == sample_pipeline_state.completed_steps
    
    def test_corrupted_file_handling(
        self,
        progress_tracker,
        temp_storage_dir
    ):
        """Test that corrupted files are handled gracefully."""
        # Create corrupted state file
        state_id = "test_corrupted_state"
        state_file = progress_tracker.states_dir / f"{state_id}.json"
        
        with open(state_file, 'w') as f:
            f.write("{ corrupted json }")
        
        # Should raise ValueError for corrupted file
        with pytest.raises(ValueError, match="Corrupted"):
            progress_tracker.load_pipeline_state(state_id)
    
    def test_legacy_data_loads_successfully(
        self,
        progress_tracker,
        temp_storage_dir
    ):
        """Test that legacy data without version field loads successfully."""
        # Create legacy state file (no version field)
        state_id = "test_legacy_state"
        state_file = progress_tracker.states_dir / f"{state_id}.json"
        
        legacy_data = {
            'state_id': state_id,
            'use_case_name': 'test',
            'current_iteration': 1,
            'completed_steps': ['step1'],
            'intermediate_results': {},
            'timestamp': '2024-01-15T10:30:00'
            # No version field
        }
        
        with open(state_file, 'w') as f:
            json.dump(legacy_data, f)
        
        # Should load successfully with migration
        loaded_state = progress_tracker.load_pipeline_state(state_id)
        
        assert loaded_state.use_case_name == 'test'
        assert loaded_state.current_iteration == 1
        assert loaded_state.completed_steps == ['step1']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
