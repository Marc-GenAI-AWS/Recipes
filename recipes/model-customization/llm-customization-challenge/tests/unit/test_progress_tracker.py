"""
Unit Tests for Progress Tracker Core Functionality

Tests cover:
- Initialization and directory creation
- Recording iteration results
- Retrieving performance history
- Saving and loading pipeline state
- Generating summary reports
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.progress_tracker import ProgressTracker
from src.config_models import IterationResult, PipelineState, Prompts


@pytest.fixture
def temp_storage_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def progress_tracker(temp_storage_dir):
    return ProgressTracker(storage_dir=temp_storage_dir)


@pytest.fixture
def sample_prompts():
    return Prompts(
        data_generation_prompt="Generate training data",
        judge_prompt="Evaluate responses"
    )


@pytest.fixture
def sample_iteration_result(sample_prompts):
    return IterationResult(
        iteration=1,
        win_rate=0.65,
        prompts_used=sample_prompts,
        training_time_seconds=3600,
        evaluation_time=datetime(2024, 1, 15, 10, 30, 0),
        model_artifact_uri="s3://bucket/model/artifact.tar.gz",
        endpoint_name="test-endpoint-1"
    )


class TestInitialization:
    def test_init_creates_directories(self, temp_storage_dir):
        tracker = ProgressTracker(storage_dir=temp_storage_dir)
        assert Path(temp_storage_dir).exists()
        assert (Path(temp_storage_dir) / "states").exists()
        assert (Path(temp_storage_dir) / "reports").exists()


class TestRecordIteration:
    def test_record_creates_file(self, progress_tracker, sample_iteration_result):
        progress_tracker.record_iteration("test_case", 1, sample_iteration_result)
        result_file = progress_tracker.storage_dir / "test_case" / "iteration_1_results.json"
        assert result_file.exists()
    
    def test_record_invalid_iteration(self, progress_tracker, sample_iteration_result):
        with pytest.raises(ValueError):
            progress_tracker.record_iteration("test_case", 0, sample_iteration_result)


class TestGetPerformanceHistory:
    def test_get_history_returns_results(self, progress_tracker, sample_prompts):
        for i in range(1, 4):
            result = IterationResult(
                iteration=i,
                win_rate=0.6 + i * 0.05,
                prompts_used=sample_prompts,
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri=f"s3://bucket/model/artifact_{i}.tar.gz",
                endpoint_name=f"test-endpoint-{i}"
            )
            progress_tracker.record_iteration("test_case", i, result)
        
        history = progress_tracker.get_performance_history("test_case")
        assert len(history) == 3


class TestPipelineState:
    def test_save_and_load_state(self, progress_tracker):
        state = PipelineState(
            use_case_name="test_case",
            current_iteration=1,
            completed_steps=["step1"],
            intermediate_results={"key": "value"},
            timestamp=datetime.now()
        )
        state_id = progress_tracker.save_pipeline_state("test_case", state)
        loaded = progress_tracker.load_pipeline_state(state_id)
        assert loaded.use_case_name == state.use_case_name


class TestSummaryReport:
    def test_generate_report(self, progress_tracker, sample_prompts):
        for i in range(1, 3):
            result = IterationResult(
                iteration=i,
                win_rate=0.6 + i * 0.05,
                prompts_used=sample_prompts,
                training_time_seconds=3600,
                evaluation_time=datetime.now(),
                model_artifact_uri=f"s3://bucket/model/artifact_{i}.tar.gz",
                endpoint_name=f"test-endpoint-{i}"
            )
            progress_tracker.record_iteration("test_case", i, result)
        
        report = progress_tracker.generate_summary_report("test_case")
        assert report.total_iterations == 2
        assert report.initial_win_rate == 0.65
