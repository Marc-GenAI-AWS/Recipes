#!/usr/bin/env python3
"""
Example script demonstrating the logging framework.

This script shows how to:
1. Configure logging
2. Use component loggers
3. Log with context
4. Create use case loggers
5. Handle errors with logging
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from src.logging_config import (
    configure_logging,
    get_logger,
    create_use_case_logger,
    log_with_context,
    LogLevel
)


def example_basic_logging():
    """Example 1: Basic logging"""
    print("\n=== Example 1: Basic Logging ===\n")
    
    logger = get_logger("example_basic")
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")


def example_context_logging():
    """Example 2: Logging with context"""
    print("\n=== Example 2: Context Logging ===\n")
    
    logger = get_logger("example_context")
    
    # Log with context data
    log_with_context(
        logger,
        LogLevel.INFO,
        "Processing batch",
        context={
            "batch_id": 123,
            "batch_size": 50,
            "total_items": 1000
        }
    )
    
    # Alternative: Use extra parameter directly
    logger.info(
        "Training completed",
        extra={
            "context": {
                "model": "llama-3.2-3b",
                "epochs": 3,
                "loss": 0.234
            }
        }
    )


def example_use_case_logger():
    """Example 3: Per-use-case logging"""
    print("\n=== Example 3: Use Case Logger ===\n")
    
    # Create a dedicated logger for a use case
    use_case_logger = create_use_case_logger(
        "customer_support_demo",
        log_dir="logs",
        level=LogLevel.DEBUG
    )
    
    use_case_logger.info("Starting pipeline execution")
    use_case_logger.debug("Loading configuration")
    use_case_logger.info("Configuration loaded successfully")
    use_case_logger.info("Pipeline execution completed")
    
    print(f"Check logs/customer_support_demo_*.log for use case logs")


def example_component_logger():
    """Example 4: Component-based logging"""
    print("\n=== Example 4: Component Logger ===\n")
    
    class DataGenerator:
        """Example component with logging"""
        
        def __init__(self):
            self.logger = get_logger("data_generator")
        
        def generate_data(self, num_examples):
            self.logger.info(f"Starting data generation for {num_examples} examples")
            
            for i in range(3):  # Simulate batches
                self.logger.debug(
                    f"Processing batch {i+1}/3",
                    extra={
                        "context": {
                            "batch": i+1,
                            "total_batches": 3
                        }
                    }
                )
                time.sleep(0.1)  # Simulate work
            
            self.logger.info("Data generation completed")
    
    generator = DataGenerator()
    generator.generate_data(150)


def example_error_handling():
    """Example 5: Error handling with logging"""
    print("\n=== Example 5: Error Handling ===\n")
    
    logger = get_logger("example_errors")
    
    def risky_operation(should_fail=False):
        """Simulate an operation that might fail"""
        if should_fail:
            raise ValueError("Simulated error")
        return "Success"
    
    # Successful operation
    try:
        logger.info("Attempting operation")
        result = risky_operation(should_fail=False)
        logger.info(f"Operation succeeded: {result}")
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
    
    # Failed operation with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Attempt {attempt + 1}/{max_retries}",
                extra={
                    "context": {
                        "attempt": attempt + 1,
                        "max_retries": max_retries
                    }
                }
            )
            
            # This will fail
            result = risky_operation(should_fail=True)
            logger.info("Operation succeeded")
            break
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(
                    f"Operation failed after {max_retries} attempts",
                    exc_info=True,
                    extra={
                        "context": {
                            "attempts": max_retries,
                            "error": str(e)
                        }
                    }
                )
            else:
                backoff = 2 ** attempt
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {backoff}s",
                    extra={
                        "context": {
                            "attempt": attempt + 1,
                            "backoff_seconds": backoff,
                            "error": str(e)
                        }
                    }
                )
                time.sleep(backoff)


def example_pipeline_simulation():
    """Example 6: Simulated pipeline execution"""
    print("\n=== Example 6: Pipeline Simulation ===\n")
    
    # Main pipeline logger
    pipeline_logger = get_logger("pipeline")
    
    # Use case logger
    use_case_name = "demo_pipeline"
    use_case_logger = create_use_case_logger(use_case_name)
    
    pipeline_logger.info(f"Starting pipeline for {use_case_name}")
    use_case_logger.info("Pipeline execution started")
    
    # Step 1: Data Generation
    log_with_context(
        use_case_logger,
        LogLevel.INFO,
        "Step 1: Data generation",
        context={"step": "data_generation", "status": "started"}
    )
    time.sleep(0.2)
    log_with_context(
        use_case_logger,
        LogLevel.INFO,
        "Data generation completed",
        context={
            "step": "data_generation",
            "status": "completed",
            "num_examples": 1000
        }
    )
    
    # Step 2: Training
    log_with_context(
        use_case_logger,
        LogLevel.INFO,
        "Step 2: Model training",
        context={"step": "training", "status": "started"}
    )
    time.sleep(0.2)
    log_with_context(
        use_case_logger,
        LogLevel.INFO,
        "Training completed",
        context={
            "step": "training",
            "status": "completed",
            "epochs": 3,
            "final_loss": 0.234
        }
    )
    
    # Step 3: Evaluation
    log_with_context(
        use_case_logger,
        LogLevel.INFO,
        "Step 3: Model evaluation",
        context={"step": "evaluation", "status": "started"}
    )
    time.sleep(0.2)
    log_with_context(
        use_case_logger,
        LogLevel.INFO,
        "Evaluation completed",
        context={
            "step": "evaluation",
            "status": "completed",
            "win_rate": 0.72
        }
    )
    
    use_case_logger.info("Pipeline execution completed successfully")
    pipeline_logger.info(f"Pipeline completed for {use_case_name}")
    
    print(f"\nCheck logs/demo_pipeline_*.log for detailed pipeline logs")


def main():
    """Run all examples"""
    print("=" * 60)
    print("Logging Framework Examples")
    print("=" * 60)
    
    # Configure logging
    configure_logging(
        log_dir="logs",
        console_level=LogLevel.INFO,
        file_level=LogLevel.DEBUG,
        enable_console=True,
        enable_file=True
    )
    
    # Run examples
    example_basic_logging()
    example_context_logging()
    example_use_case_logger()
    example_component_logger()
    example_error_handling()
    example_pipeline_simulation()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("Check the logs/ directory for log files:")
    print("  - logs/pipeline.log (main log with all messages)")
    print("  - logs/customer_support_demo_*.log (use case log)")
    print("  - logs/demo_pipeline_*.log (pipeline simulation log)")
    print("=" * 60)


if __name__ == "__main__":
    main()
