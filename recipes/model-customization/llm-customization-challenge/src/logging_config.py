"""
Logging configuration module for the automated LLM finetuning pipeline.

This module provides structured logging with:
- Timestamp, level, component, message, and context
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- File-based logging to logs/ directory
- Console logging for development
- JSON format for structured logs
- Per-use-case log files
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from enum import Enum


class LogLevel(Enum):
    """Log levels for the pipeline"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in structured JSON format.
    
    Each log record includes:
    - timestamp: ISO 8601 formatted timestamp
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - component: Name of the logger (typically module name)
    - message: Log message
    - context: Additional context data (if provided)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        
        # Add context if available
        if hasattr(record, "context") and record.context:
            log_data["context"] = record.context
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName",
                "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "context"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.
    
    Formats logs as: timestamp - level - component - message
    """
    
    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s - %(levelname)-8s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


class PipelineLogger:
    """
    Main logging configuration class for the pipeline.
    
    Provides methods to:
    - Configure logging for the entire application
    - Get loggers for specific components
    - Create per-use-case log files
    - Add context to log messages
    """
    
    _configured = False
    _loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def configure(
        cls,
        log_dir: str = "logs",
        console_level: LogLevel = LogLevel.INFO,
        file_level: LogLevel = LogLevel.DEBUG,
        enable_console: bool = True,
        enable_file: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5
    ) -> None:
        """
        Configure logging for the entire application.
        
        Args:
            log_dir: Directory for log files
            console_level: Minimum log level for console output
            file_level: Minimum log level for file output
            enable_console: Whether to enable console logging
            enable_file: Whether to enable file logging
            max_bytes: Maximum size of each log file before rotation
            backup_count: Number of backup log files to keep
        """
        if cls._configured:
            return
        
        # Create log directory
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture all levels
        
        # Remove existing handlers
        root_logger.handlers.clear()
        
        # Add console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(console_level.value)
            console_handler.setFormatter(ConsoleFormatter())
            root_logger.addHandler(console_handler)
        
        # Add file handler with rotation
        if enable_file:
            main_log_file = log_path / "pipeline.log"
            file_handler = logging.handlers.RotatingFileHandler(
                main_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
            file_handler.setLevel(file_level.value)
            file_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(file_handler)
        
        cls._configured = True
        
        # Log configuration complete
        logger = cls.get_logger("logging_config")
        logger.info(
            "Logging configured",
            extra={
                "context": {
                    "log_dir": str(log_path),
                    "console_level": console_level.name,
                    "file_level": file_level.name,
                    "enable_console": enable_console,
                    "enable_file": enable_file
                }
            }
        )
    
    @classmethod
    def get_logger(cls, component: str) -> logging.Logger:
        """
        Get a logger for a specific component.
        
        Args:
            component: Name of the component (typically module name)
            
        Returns:
            Logger instance for the component
        """
        if not cls._configured:
            cls.configure()
        
        if component not in cls._loggers:
            cls._loggers[component] = logging.getLogger(component)
        
        return cls._loggers[component]
    
    @classmethod
    def create_use_case_logger(
        cls,
        use_case_name: str,
        log_dir: str = "logs",
        level: LogLevel = LogLevel.DEBUG
    ) -> logging.Logger:
        """
        Create a dedicated logger for a specific use case.
        
        This creates a separate log file for the use case in addition
        to the main pipeline log.
        
        Args:
            use_case_name: Name of the use case
            log_dir: Directory for log files
            level: Minimum log level for this logger
            
        Returns:
            Logger instance for the use case
        """
        if not cls._configured:
            cls.configure()
        
        logger_name = f"use_case.{use_case_name}"
        
        if logger_name in cls._loggers:
            return cls._loggers[logger_name]
        
        # Create logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(level.value)
        
        # Create use case log file
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        use_case_log_file = log_path / f"{use_case_name}_{timestamp}.log"
        
        # Add file handler for use case
        file_handler = logging.handlers.RotatingFileHandler(
            use_case_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(level.value)
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
        
        cls._loggers[logger_name] = logger
        
        logger.info(
            f"Use case logger created for {use_case_name}",
            extra={
                "context": {
                    "use_case": use_case_name,
                    "log_file": str(use_case_log_file)
                }
            }
        )
        
        return logger
    
    @classmethod
    def log_with_context(
        cls,
        logger: logging.Logger,
        level: LogLevel,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """
        Log a message with additional context.
        
        Args:
            logger: Logger instance to use
            level: Log level
            message: Log message
            context: Additional context data
            **kwargs: Additional keyword arguments for the log call
        """
        extra = kwargs.get("extra", {})
        if context:
            extra["context"] = context
        kwargs["extra"] = extra
        
        logger.log(level.value, message, **kwargs)
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset logging configuration.
        
        This is primarily for testing purposes.
        """
        cls._configured = False
        cls._loggers.clear()
        
        # Clear all handlers from root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)


# Convenience functions for common logging patterns

def get_logger(component: str) -> logging.Logger:
    """
    Get a logger for a component.
    
    Args:
        component: Component name
        
    Returns:
        Logger instance
    """
    return PipelineLogger.get_logger(component)


def configure_logging(
    log_dir: str = "logs",
    console_level: LogLevel = LogLevel.INFO,
    file_level: LogLevel = LogLevel.DEBUG,
    enable_console: bool = True,
    enable_file: bool = True
) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_dir: Directory for log files
        console_level: Minimum log level for console output
        file_level: Minimum log level for file output
        enable_console: Whether to enable console logging
        enable_file: Whether to enable file logging
    """
    PipelineLogger.configure(
        log_dir=log_dir,
        console_level=console_level,
        file_level=file_level,
        enable_console=enable_console,
        enable_file=enable_file
    )


def create_use_case_logger(
    use_case_name: str,
    log_dir: str = "logs",
    level: LogLevel = LogLevel.DEBUG
) -> logging.Logger:
    """
    Create a logger for a specific use case.
    
    Args:
        use_case_name: Name of the use case
        log_dir: Directory for log files
        level: Minimum log level
        
    Returns:
        Logger instance
    """
    return PipelineLogger.create_use_case_logger(
        use_case_name=use_case_name,
        log_dir=log_dir,
        level=level
    )


def log_with_context(
    logger: logging.Logger,
    level: LogLevel,
    message: str,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a message with context.
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        context: Additional context data
    """
    PipelineLogger.log_with_context(
        logger=logger,
        level=level,
        message=message,
        context=context
    )
