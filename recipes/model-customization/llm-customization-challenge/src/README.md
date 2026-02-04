# Source Code Directory

This directory contains all source code for the automated LLM finetuning pipeline.

## Structure

The source code is organized into the following components:

- **Configuration Manager**: Manages use case definitions and pipeline configurations
- **Synthetic Data Generator**: Generates training data using Claude Sonnet 4
- **Model Trainer**: Finetunes Llama models on AWS SageMaker
- **Model Deployer**: Deploys finetuned models to SageMaker endpoints
- **Inference Engine**: Generates responses from finetuned and baseline models
- **Judge**: Evaluates response quality using Claude Sonnet 4
- **Self-Improvement Agent**: Analyzes results and optimizes prompts
- **Progress Tracker**: Tracks performance and saves pipeline state
- **Pipeline Orchestrator**: Coordinates execution of all pipeline steps
- **Streamlit UI**: Web-based user interface for pipeline operation

## Development

All source files should include:
- Type hints for all function parameters and return values
- Comprehensive docstrings
- Error handling with appropriate logging
- Unit tests in the corresponding tests/unit/ directory
