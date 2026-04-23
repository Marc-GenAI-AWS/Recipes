"""
Unit tests for the logging configuration module.

Tests cover:
- Logger configuration and initialization
- Structured JSON formatting
- Console formatting
- Per-use-case log files
- Log rotation
- Context logging
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import List

import pytest

from src.logging_config import (
    PipelineLogger,
    StructuredFormatter,
    ConsoleFormatter,
    LogLevel,
    get_logger,
    configure_logging,
    create_use_case_logger,
    log_with_context
)


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary directory for log files"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration before and after each test"""
    PipelineLogger.reset()
    yield
    PipelineLogger.reset()


class TestStructuredFormatter:
    """Tests for StructuredFormatter"""
    
    def test_basic_formatting(self):
        """Test basic log record formatting"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_component",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert "timestamp" in log_data
        assert log_data["level"] == "INFO"
        assert log_data["component"] == "test_component"
        assert log_data["message"] == "Test message"
    
    def test_formatting_with_context(self):
        """Test log formatting with context data"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_component",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {"use_case": "test", "iteration": 1}
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert "context" in log_data
        assert log_data["context"]["use_case"] == "test"
        assert log_data["context"]["iteration"] == 1
    
    def test_formatting_with_exception(self):
        """Test log formatting with exception info"""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test_component",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert "exception" in log_data
        assert "ValueError: Test error" in log_data["exception"]


class TestConsoleFormatter:
    """Tests for ConsoleFormatter"""
    
    def test_console_formatting(self):
        """Test console log formatting"""
        formatter = ConsoleFormatter()
        record = logging.LogRecord(
            name="test_component",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        assert "INFO" in formatted
        assert "test_component" in formatted
        assert "Test message" in formatted


class TestPipelineLogger:
    """Tests for PipelineLogger class"""
    
    def test_configure_creates_log_directory(self, temp_log_dir):
        """Test that configure creates the log directory"""
        log_dir = temp_log_dir / "new_logs"
        assert not log_dir.exists()
        
        PipelineLogger.configure(log_dir=str(log_dir))
        
        assert log_dir.exists()
    
    def test_configure_creates_main_log_file(self, temp_log_dir):
        """Test that configure creates the main log file"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        main_log = temp_log_dir / "pipeline.log"
        assert main_log.exists()
    
    def test_configure_only_once(self, temp_log_dir):
        """Test that configure only runs once"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        # Get handler count
        root_logger = logging.getLogger()
        handler_count = len(root_logger.handlers)
        
        # Configure again
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        # Handler count should be the same
        assert len(root_logger.handlers) == handler_count
    
    def test_get_logger_returns_logger(self, temp_log_dir):
        """Test that get_logger returns a logger instance"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        logger = PipelineLogger.get_logger("test_component")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_component"
    
    def test_get_logger_caches_loggers(self, temp_log_dir):
        """Test that get_logger caches logger instances"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        logger1 = PipelineLogger.get_logger("test_component")
        logger2 = PipelineLogger.get_logger("test_component")
        
        assert logger1 is logger2
    
    def test_create_use_case_logger(self, temp_log_dir):
        """Test creating a use case logger"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        logger = PipelineLogger.create_use_case_logger(
            "test_use_case",
            log_dir=str(temp_log_dir)
        )
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "use_case.test_use_case"
        
        # Check that use case log file was created
        log_files = list(temp_log_dir.glob("test_use_case_*.log"))
        assert len(log_files) == 1
    
    def test_log_with_context(self, temp_log_dir):
        """Test logging with context"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test_component")
        
        context = {"use_case": "test", "iteration": 1}
        PipelineLogger.log_with_context(
            logger,
            LogLevel.INFO,
            "Test message",
            context=context
        )
        
        # Read log file and verify context
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["message"] == "Test message"
        assert log_data["context"]["use_case"] == "test"
        assert log_data["context"]["iteration"] == 1


class TestLoggingLevels:
    """Tests for different log levels"""
    
    def test_debug_level(self, temp_log_dir):
        """Test DEBUG level logging"""
        PipelineLogger.configure(
            log_dir=str(temp_log_dir),
            file_level=LogLevel.DEBUG
        )
        logger = PipelineLogger.get_logger("test")
        
        logger.debug("Debug message")
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            # Read debug message
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["level"] == "DEBUG"
        assert log_data["message"] == "Debug message"
    
    def test_info_level(self, temp_log_dir):
        """Test INFO level logging"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test")
        
        logger.info("Info message")
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Info message"
    
    def test_warning_level(self, temp_log_dir):
        """Test WARNING level logging"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test")
        
        logger.warning("Warning message")
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["level"] == "WARNING"
        assert log_data["message"] == "Warning message"
    
    def test_error_level(self, temp_log_dir):
        """Test ERROR level logging"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test")
        
        logger.error("Error message")
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["level"] == "ERROR"
        assert log_data["message"] == "Error message"
    
    def test_critical_level(self, temp_log_dir):
        """Test CRITICAL level logging"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test")
        
        logger.critical("Critical message")
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["level"] == "CRITICAL"
        assert log_data["message"] == "Critical message"


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def test_get_logger_function(self, temp_log_dir):
        """Test get_logger convenience function"""
        configure_logging(log_dir=str(temp_log_dir))
        
        logger = get_logger("test_component")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_component"
    
    def test_configure_logging_function(self, temp_log_dir):
        """Test configure_logging convenience function"""
        configure_logging(
            log_dir=str(temp_log_dir),
            console_level=LogLevel.WARNING,
            file_level=LogLevel.DEBUG
        )
        
        main_log = temp_log_dir / "pipeline.log"
        assert main_log.exists()
    
    def test_create_use_case_logger_function(self, temp_log_dir):
        """Test create_use_case_logger convenience function"""
        configure_logging(log_dir=str(temp_log_dir))
        
        logger = create_use_case_logger(
            "test_use_case",
            log_dir=str(temp_log_dir)
        )
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "use_case.test_use_case"
    
    def test_log_with_context_function(self, temp_log_dir):
        """Test log_with_context convenience function"""
        configure_logging(log_dir=str(temp_log_dir))
        logger = get_logger("test")
        
        log_with_context(
            logger,
            LogLevel.INFO,
            "Test message",
            context={"key": "value"}
        )
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["message"] == "Test message"
        assert log_data["context"]["key"] == "value"


class TestLogRotation:
    """Tests for log file rotation"""
    
    def test_log_rotation_on_size(self, temp_log_dir):
        """Test that logs rotate when size limit is reached"""
        # Configure with small max size
        PipelineLogger.configure(
            log_dir=str(temp_log_dir),
            max_bytes=1024,  # 1 KB
            backup_count=2
        )
        logger = PipelineLogger.get_logger("test")
        
        # Write enough logs to trigger rotation
        large_message = "x" * 200
        for i in range(10):
            logger.info(f"Message {i}: {large_message}")
        
        # Check that backup files were created
        log_files = list(temp_log_dir.glob("pipeline.log*"))
        assert len(log_files) > 1


class TestMultipleLoggers:
    """Tests for multiple logger instances"""
    
    def test_multiple_component_loggers(self, temp_log_dir):
        """Test creating multiple component loggers"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        logger1 = PipelineLogger.get_logger("component1")
        logger2 = PipelineLogger.get_logger("component2")
        
        logger1.info("Message from component1")
        logger2.info("Message from component2")
        
        # Read log file
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            lines = f.readlines()
        
        # Skip configuration message
        log_data1 = json.loads(lines[1])
        log_data2 = json.loads(lines[2])
        
        assert log_data1["component"] == "component1"
        assert log_data2["component"] == "component2"
    
    def test_multiple_use_case_loggers(self, temp_log_dir):
        """Test creating multiple use case loggers"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        
        logger1 = PipelineLogger.create_use_case_logger(
            "use_case1",
            log_dir=str(temp_log_dir)
        )
        logger2 = PipelineLogger.create_use_case_logger(
            "use_case2",
            log_dir=str(temp_log_dir)
        )
        
        logger1.info("Message from use_case1")
        logger2.info("Message from use_case2")
        
        # Check that separate log files were created
        log_files1 = list(temp_log_dir.glob("use_case1_*.log"))
        log_files2 = list(temp_log_dir.glob("use_case2_*.log"))
        
        assert len(log_files1) == 1
        assert len(log_files2) == 1


class TestConsoleAndFileLogging:
    """Tests for console and file logging configuration"""
    
    def test_console_only(self, temp_log_dir, capsys):
        """Test console-only logging"""
        PipelineLogger.configure(
            log_dir=str(temp_log_dir),
            enable_console=True,
            enable_file=False
        )
        logger = PipelineLogger.get_logger("test")
        
        logger.info("Console message")
        
        captured = capsys.readouterr()
        assert "Console message" in captured.out
        
        # File should not be created
        main_log = temp_log_dir / "pipeline.log"
        assert not main_log.exists()
    
    def test_file_only(self, temp_log_dir, capsys):
        """Test file-only logging"""
        PipelineLogger.configure(
            log_dir=str(temp_log_dir),
            enable_console=False,
            enable_file=True
        )
        logger = PipelineLogger.get_logger("test")
        
        logger.info("File message")
        
        captured = capsys.readouterr()
        # Message should not appear in console
        assert "File message" not in captured.out
        
        # But should be in file
        main_log = temp_log_dir / "pipeline.log"
        assert main_log.exists()
        with open(main_log, "r") as f:
            content = f.read()
            assert "File message" in content
    
    def test_both_console_and_file(self, temp_log_dir, capsys):
        """Test both console and file logging"""
        PipelineLogger.configure(
            log_dir=str(temp_log_dir),
            enable_console=True,
            enable_file=True
        )
        logger = PipelineLogger.get_logger("test")
        
        logger.info("Both message")
        
        # Check console
        captured = capsys.readouterr()
        assert "Both message" in captured.out
        
        # Check file
        main_log = temp_log_dir / "pipeline.log"
        assert main_log.exists()
        with open(main_log, "r") as f:
            content = f.read()
            assert "Both message" in content


class TestEdgeCases:
    """Tests for edge cases and error conditions"""
    
    def test_empty_message(self, temp_log_dir):
        """Test logging empty message"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test")
        
        logger.info("")
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["message"] == ""
    
    def test_unicode_message(self, temp_log_dir):
        """Test logging unicode message"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test")
        
        unicode_msg = "Test message with unicode: 你好 🎉"
        logger.info(unicode_msg)
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r", encoding="utf-8") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["message"] == unicode_msg
    
    def test_special_characters_in_context(self, temp_log_dir):
        """Test logging with special characters in context"""
        PipelineLogger.configure(log_dir=str(temp_log_dir))
        logger = PipelineLogger.get_logger("test")
        
        context = {
            "key": "value with \"quotes\"",
            "newline": "value\nwith\nnewlines"
        }
        PipelineLogger.log_with_context(
            logger,
            LogLevel.INFO,
            "Test",
            context=context
        )
        
        main_log = temp_log_dir / "pipeline.log"
        with open(main_log, "r") as f:
            # Skip configuration message
            f.readline()
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        assert log_data["context"]["key"] == "value with \"quotes\""
        assert log_data["context"]["newline"] == "value\nwith\nnewlines"
