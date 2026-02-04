# Logging Guide

This guide explains how to use the structured logging framework in the automated LLM finetuning pipeline.

## Overview

The logging framework provides:

- **Structured logging** with JSON format for machine parsing
- **Multiple log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **File-based logging** with automatic rotation
- **Console logging** for development
- **Per-use-case log files** for tracking specific pipeline runs
- **Context-aware logging** for adding metadata to log messages

## Quick Start

### Basic Configuration

```python
from src.logging_config import configure_logging, get_logger, LogLevel

# Configure logging (call once at application startup)
configure_logging(
    log_dir="logs",
    console_level=LogLevel.INFO,
    file_level=LogLevel.DEBUG
)

# Get a logger for your component
logger = get_logger("my_component")

# Log messages
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error")
```

### Logging with Context

Add structured context data to your log messages:

```python
from src.logging_config import get_logger, log_with_context, LogLevel

logger = get_logger("data_generator")

# Log with context
log_with_context(
    logger,
    LogLevel.INFO,
    "Training data generated",
    context={
        "use_case": "customer_support",
        "num_examples": 1000,
        "batch_size": 50
    }
)
```

### Per-Use-Case Logging

Create dedicated log files for specific use cases:

```python
from src.logging_config import create_use_case_logger

# Create a logger for a specific use case
use_case_logger = create_use_case_logger(
    "customer_support",
    log_dir="logs",
    level=LogLevel.DEBUG
)

# This will create a file like: logs/customer_support_20240117_143022.log
use_case_logger.info("Starting pipeline for customer support use case")
```

## Configuration Options

### PipelineLogger.configure()

```python
from src.logging_config import PipelineLogger, LogLevel

PipelineLogger.configure(
    log_dir="logs",              # Directory for log files
    console_level=LogLevel.INFO, # Minimum level for console output
    file_level=LogLevel.DEBUG,   # Minimum level for file output
    enable_console=True,         # Enable console logging
    enable_file=True,            # Enable file logging
    max_bytes=10*1024*1024,      # Max log file size (10 MB)
    backup_count=5               # Number of backup files to keep
)
```

### Log Levels

- **DEBUG**: Detailed information for diagnosing problems
- **INFO**: General informational messages
- **WARNING**: Warning messages for potentially problematic situations
- **ERROR**: Error messages for serious problems
- **CRITICAL**: Critical messages for very serious errors

## Log Format

### Structured JSON Format (File Logs)

Log files use JSON format for easy parsing:

```json
{
  "timestamp": "2024-01-17T14:30:22.123456Z",
  "level": "INFO",
  "component": "data_generator",
  "message": "Training data generated",
  "context": {
    "use_case": "customer_support",
    "num_examples": 1000,
    "batch_size": 50
  }
}
```

### Human-Readable Format (Console Logs)

Console logs use a readable format:

```
2024-01-17 14:30:22 - INFO     - data_generator - Training data generated
```

## Usage Examples

### Example 1: Component Logger

```python
from src.logging_config import get_logger

class SyntheticDataGenerator:
    def __init__(self):
        self.logger = get_logger("synthetic_data_generator")
    
    def generate_training_data(self, use_case, num_examples):
        self.logger.info(
            f"Starting data generation for {use_case.name}",
            extra={
                "context": {
                    "use_case": use_case.name,
                    "num_examples": num_examples
                }
            }
        )
        
        try:
            # Generate data...
            self.logger.info("Data generation completed successfully")
        except Exception as e:
            self.logger.error(
                f"Data generation failed: {e}",
                exc_info=True,
                extra={
                    "context": {
                        "use_case": use_case.name,
                        "error": str(e)
                    }
                }
            )
            raise
```

### Example 2: Pipeline Orchestrator

```python
from src.logging_config import get_logger, create_use_case_logger, log_with_context, LogLevel

class FinetuningPipeline:
    def __init__(self):
        self.logger = get_logger("pipeline_orchestrator")
    
    def run(self, use_case_name):
        # Create use case logger
        use_case_logger = create_use_case_logger(use_case_name)
        
        self.logger.info(f"Starting pipeline for {use_case_name}")
        use_case_logger.info("Pipeline execution started")
        
        try:
            # Execute pipeline steps
            self._execute_data_generation(use_case_logger)
            self._execute_training(use_case_logger)
            self._execute_evaluation(use_case_logger)
            
            use_case_logger.info("Pipeline execution completed successfully")
            self.logger.info(f"Pipeline completed for {use_case_name}")
            
        except Exception as e:
            use_case_logger.error(
                f"Pipeline failed: {e}",
                exc_info=True
            )
            self.logger.error(
                f"Pipeline failed for {use_case_name}: {e}",
                exc_info=True
            )
            raise
    
    def _execute_data_generation(self, logger):
        log_with_context(
            logger,
            LogLevel.INFO,
            "Executing data generation step",
            context={"step": "data_generation"}
        )
        # Implementation...
```

### Example 3: Error Handling with Logging

```python
from src.logging_config import get_logger
import time

logger = get_logger("model_trainer")

def train_model_with_retry(training_data, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Training attempt {attempt + 1}/{max_retries}",
                extra={
                    "context": {
                        "attempt": attempt + 1,
                        "max_retries": max_retries
                    }
                }
            )
            
            # Train model...
            result = train_model(training_data)
            
            logger.info("Training completed successfully")
            return result
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(
                    f"Training failed after {max_retries} attempts",
                    exc_info=True,
                    extra={
                        "context": {
                            "attempts": max_retries,
                            "error": str(e)
                        }
                    }
                )
                raise
            
            backoff = 2 ** attempt
            logger.warning(
                f"Training attempt {attempt + 1} failed, retrying in {backoff}s",
                extra={
                    "context": {
                        "attempt": attempt + 1,
                        "backoff_seconds": backoff,
                        "error": str(e)
                    }
                }
            )
            time.sleep(backoff)
```

## Log File Organization

The logging framework creates the following structure:

```
logs/
├── pipeline.log              # Main pipeline log (all components)
├── pipeline.log.1            # Rotated backup
├── pipeline.log.2            # Rotated backup
├── customer_support_20240117_143022.log  # Use case log
├── code_review_20240117_150033.log       # Use case log
└── ...
```

## Best Practices

### 1. Use Appropriate Log Levels

- **DEBUG**: Detailed diagnostic information (e.g., variable values, loop iterations)
- **INFO**: Normal operation events (e.g., "Pipeline started", "Training completed")
- **WARNING**: Unexpected but recoverable situations (e.g., "Retry attempt 2/3")
- **ERROR**: Errors that prevent a specific operation (e.g., "Training failed")
- **CRITICAL**: Errors that may cause the entire application to fail

### 2. Add Context to Important Logs

```python
# Good: Includes context
logger.info(
    "Model deployed",
    extra={
        "context": {
            "endpoint_name": endpoint_name,
            "model_version": version,
            "instance_type": instance_type
        }
    }
)

# Less useful: No context
logger.info("Model deployed")
```

### 3. Log Exceptions with Stack Traces

```python
try:
    # Some operation
    pass
except Exception as e:
    logger.error(
        f"Operation failed: {e}",
        exc_info=True  # Include stack trace
    )
```

### 4. Use Component-Specific Loggers

```python
# Good: Component-specific logger
class DataGenerator:
    def __init__(self):
        self.logger = get_logger("data_generator")

# Avoid: Using root logger
import logging
logger = logging.getLogger()  # Don't do this
```

### 5. Create Use Case Loggers for Pipeline Runs

```python
# Create a dedicated logger for each pipeline run
use_case_logger = create_use_case_logger(use_case_name)

# Use it throughout the pipeline execution
use_case_logger.info("Step 1: Data generation")
use_case_logger.info("Step 2: Training")
use_case_logger.info("Step 3: Evaluation")
```

## Testing with Logging

When writing tests, you can reset the logging configuration:

```python
import pytest
from src.logging_config import PipelineLogger

@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging before and after each test"""
    PipelineLogger.reset()
    yield
    PipelineLogger.reset()
```

## Troubleshooting

### Issue: Logs not appearing in file

**Solution**: Ensure logging is configured before creating loggers:

```python
# Configure first
configure_logging()

# Then get loggers
logger = get_logger("my_component")
```

### Issue: Too many log files

**Solution**: Adjust rotation settings:

```python
PipelineLogger.configure(
    max_bytes=50*1024*1024,  # Increase max file size
    backup_count=3           # Reduce backup count
)
```

### Issue: Console too verbose

**Solution**: Increase console log level:

```python
configure_logging(
    console_level=LogLevel.WARNING,  # Only show warnings and errors
    file_level=LogLevel.DEBUG        # Keep detailed file logs
)
```

## Advanced Usage

### Custom Log Formatting

If you need custom formatting, you can create your own formatter:

```python
import logging
from src.logging_config import PipelineLogger

class CustomFormatter(logging.Formatter):
    def format(self, record):
        # Custom formatting logic
        return f"[{record.levelname}] {record.name}: {record.getMessage()}"

# Configure with custom formatter
PipelineLogger.configure()
logger = PipelineLogger.get_logger("my_component")

# Add custom handler
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
logger.addHandler(handler)
```

### Filtering Logs

You can filter logs by level or content:

```python
import logging

class ErrorOnlyFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.ERROR

# Add filter to handler
logger = get_logger("my_component")
for handler in logger.handlers:
    handler.addFilter(ErrorOnlyFilter())
```

## Summary

The logging framework provides a robust, structured logging solution for the pipeline:

- ✅ Structured JSON logs for machine parsing
- ✅ Human-readable console output
- ✅ Automatic log rotation
- ✅ Per-use-case log files
- ✅ Context-aware logging
- ✅ Multiple log levels
- ✅ Easy configuration

For more information, see the source code in `src/logging_config.py` and tests in `tests/unit/test_logging_config.py`.
