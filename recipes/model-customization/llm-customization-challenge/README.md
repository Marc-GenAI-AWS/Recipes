# SageMaker AI LLM Model Customization Challenge Automation

An automated system for finetuning small language models with self-improvement capabilities. This pipeline orchestrates synthetic data generation, model training on AWS SageMaker, deployment, evaluation against baseline models, and iterative improvement through automated prompt optimization.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
  - [How Self-Improvement Works](#how-self-improvement-works)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the Pipeline](#running-the-pipeline)
- [Security](#security)
- [Project Structure](#project-structure)
- [Use Case Management](#use-case-management)
  - [Creating a Use Case](#creating-a-use-case)
- [Configuration](#configuration)
  - [Pipeline Configuration](#pipeline-configuration)
  - [Configuration Parameters Explained](#configuration-parameters-explained)
  - [Environment Variables](#environment-variables)
- [Testing](#testing)
  - [Running Tests](#running-tests)
  - [Test Categories](#test-categories)
  - [Writing Tests](#writing-tests)
- [Development](#development)
  - [Setting Up Development Environment](#setting-up-development-environment)
  - [Development Workflow](#development-workflow)
  - [Code Quality Tools](#code-quality-tools)
- [Documentation](#documentation)
- [AWS Resources](#aws-resources)
- [Troubleshooting](#troubleshooting)
- [Frequently Asked Questions (FAQ)](#frequently-asked-questions-faq)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Overview

The Automated LLM Finetuning Pipeline streamlines the complete lifecycle of model finetuning:

1. **Synthetic Data Generation**: Uses Claude Sonnet 4 to generate high-quality training data
2. **Model Training**: Finetunes Llama 3.2 3B models on AWS SageMaker with LoRA
3. **Model Deployment**: Deploys finetuned models to SageMaker endpoints
4. **Automated Evaluation**: Compares finetuned model responses against 70B baseline using Claude as judge
5. **Self-Improvement**: Automatically optimizes prompts when performance is below threshold
6. **Web Interface**: Streamlit-based UI for managing use cases and monitoring pipelines

## Key Features

- 🤖 **Fully Automated**: Run complete finetuning pipeline with a single command
- 🔄 **Self-Improving**: Automatically optimizes prompts when win rate is below threshold
- 📊 **Performance Tracking**: Track win rates and improvements across iterations
- 🌐 **Web Interface**: User-friendly Streamlit UI for all operations
- 💾 **Resumable**: Save progress and resume from interruptions
- 🧪 **Well-Tested**: Comprehensive unit and property-based tests
- ☁️ **AWS Native**: Built on SageMaker, Bedrock, and S3

### How Self-Improvement Works

The pipeline includes an intelligent self-improvement loop that automatically optimizes performance:

1. **Initial Run**: Pipeline generates training data, trains model, and evaluates against baseline
2. **Performance Check**: If win rate < threshold (e.g., 60%), trigger self-improvement
3. **Failure Analysis**: Self-improvement agent analyzes losing judgments to identify patterns
4. **Prompt Optimization**: Agent generates improved prompts for data generation and judging
5. **Re-run**: Pipeline automatically re-runs with optimized prompts
6. **Iteration**: Process repeats up to max iterations (default: 5) or until threshold is met

**Example**:
- Iteration 1: Win rate 45% → Self-improvement triggered
- Iteration 2: Win rate 58% → Self-improvement triggered
- Iteration 3: Win rate 67% → Success! Pipeline completes

This automated optimization eliminates manual prompt engineering and consistently improves model performance.

## Architecture

```
User → Streamlit UI → Pipeline Orchestrator
                           ↓
    ┌──────────────────────┼──────────────────────┐
    ↓                      ↓                      ↓
Config Manager    Synthetic Data Gen      Model Trainer
    ↓                      ↓                      ↓
Progress Tracker    Model Deployer        Inference Engine
    ↓                      ↓                      ↓
Self-Improvement    Judge (Claude)        AWS Services
```

## Quick Start

### Prerequisites

- Python 3.10 or higher
- AWS account with SageMaker, Bedrock, and S3 access
- Windows OS (for these instructions)

### Installation

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/yourusername/SageMaker-AI-LLM-Model-Customization-Challenge-Automation.git
   cd SageMaker-AI-LLM-Model-Customization-Challenge-Automation
   ```

2. **Set up virtual environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Set up configuration**:
   - Copy `config/pipeline_config.yaml.template` to `config/pipeline_config.yaml`
   - Update with your AWS settings (region, role ARN, S3 bucket)

5. **Configure AWS credentials** (see detailed guide below):
   ```powershell
   aws configure
   ```

### 🔐 Setting Up AWS Credentials

This section explains how to configure AWS credentials to run the application. **Your credentials are never stored in the project** - they're managed securely by AWS CLI or environment variables.

#### Option 1: AWS CLI Configuration (Recommended)

This is the easiest and most secure method for local development.

1. **Install AWS CLI** (if not already installed):
   ```powershell
   # Download from: https://aws.amazon.com/cli/
   # Or use winget:
   winget install Amazon.AWSCLI
   ```

2. **Configure your credentials**:
   ```powershell
   aws configure
   ```
   
   You'll be prompted for:
   - **AWS Access Key ID**: Your access key (starts with `AKIA...`)
   - **AWS Secret Access Key**: Your secret key
   - **Default region**: e.g., `us-east-1`
   - **Default output format**: `json` (recommended)

3. **Verify configuration**:
   ```powershell
   # Test AWS credentials
   aws sts get-caller-identity
   
   # Test Bedrock access
   python validate_bedrock_connection.py
   ```

**Where are credentials stored?**
- Windows: `C:\Users\<YourUsername>\.aws\credentials`
- This file is **outside your project directory** and **never committed to git**

#### Option 2: Environment Variables

Use this for temporary credentials or CI/CD environments.

```powershell
# Set credentials for current session
$env:AWS_ACCESS_KEY_ID = "your-access-key-id"
$env:AWS_SECRET_ACCESS_KEY = "your-secret-access-key"
$env:AWS_REGION = "us-east-1"

# Optional: Session token for temporary credentials
$env:AWS_SESSION_TOKEN = "your-session-token"

# Verify
aws sts get-caller-identity
```

**Note**: These credentials only last for your current PowerShell session.

#### Option 3: AWS Profiles (Multiple Accounts)

Use profiles if you work with multiple AWS accounts.

1. **Configure a named profile**:
   ```powershell
   aws configure --profile my-project
   ```

2. **Use the profile**:
   ```powershell
   # Set profile for current session
   $env:AWS_PROFILE = "my-project"
   
   # Or specify in each command
   aws s3 ls --profile my-project
   ```

3. **Run the application with profile**:
   ```powershell
   $env:AWS_PROFILE = "my-project"
   streamlit run streamlit_app.py
   ```

#### Option 4: IAM Roles (Production/EC2)

For production deployments on AWS infrastructure (EC2, ECS, Lambda), use IAM roles instead of credentials.

**Benefits**:
- No credentials to manage
- Automatic credential rotation
- Better security

**Setup**:
1. Attach an IAM role to your EC2 instance/ECS task
2. Grant the role necessary permissions (SageMaker, Bedrock, S3)
3. Application automatically uses the role credentials

#### Getting AWS Credentials

If you don't have AWS credentials yet:

1. **Sign in to AWS Console**: https://console.aws.amazon.com/
2. **Navigate to IAM**: Services → IAM → Users
3. **Create or select your user**
4. **Security credentials tab** → Create access key
5. **Choose use case**: "Command Line Interface (CLI)"
6. **Download credentials**: Save the Access Key ID and Secret Access Key

**⚠️ Security Warning**: 
- Never share your secret access key
- Never commit credentials to git
- Rotate keys regularly
- Use least-privilege permissions

#### Required AWS Permissions

Your AWS credentials need access to these services:

- **Amazon Bedrock**: For Claude Sonnet 4 (data generation and judging)
  - `bedrock:InvokeModel`
  - `bedrock:ListFoundationModels`

- **Amazon SageMaker**: For model training and deployment
  - `sagemaker:CreateTrainingJob`
  - `sagemaker:CreateModel`
  - `sagemaker:CreateEndpoint`
  - `sagemaker:DescribeTrainingJob`
  - `sagemaker:DescribeEndpoint`

- **Amazon S3**: For storing training data and model artifacts
  - `s3:PutObject`
  - `s3:GetObject`
  - `s3:ListBucket`

- **IAM**: For passing SageMaker execution role
  - `iam:PassRole`

See `config/aws/policies/` for example IAM policies.

#### Verifying Your Setup

After configuring credentials, verify everything works:

```powershell
# 1. Check AWS identity
aws sts get-caller-identity

# 2. Test Bedrock access
python validate_bedrock_connection.py

# 3. List available Bedrock models
python list_bedrock_models.py

# 4. Check SageMaker access
aws sagemaker list-training-jobs --max-results 5

# 5. Check S3 access (replace with your bucket)
aws s3 ls s3://your-bucket-name/
```

If all commands succeed, you're ready to run the application!

#### Troubleshooting Credentials

**"Unable to locate credentials"**
- Run `aws configure` to set up credentials
- Check that `~/.aws/credentials` file exists
- Verify environment variables are set (if using that method)

**"Access Denied" errors**
- Check IAM permissions for your user/role
- Verify the service is available in your region
- Ensure you're using the correct AWS account

**"Region not found"**
- Set AWS region: `$env:AWS_REGION = "us-east-1"`
- Or configure default region: `aws configure set region us-east-1`

**Credentials work in CLI but not in application**
- Restart your terminal/IDE after configuring credentials
- Check that virtual environment is activated
- Verify no conflicting environment variables

#### Security Best Practices

✅ **DO**:
- Store credentials in `~/.aws/credentials` (outside project)
- Use IAM roles for production deployments
- Rotate access keys regularly (every 90 days)
- Use least-privilege permissions
- Enable MFA on your AWS account

❌ **DON'T**:
- Commit credentials to git
- Share credentials via email/chat
- Use root account credentials
- Store credentials in code files
- Use overly permissive policies

**Before pushing to GitHub:**
```powershell
# Run security check
python scripts/check_security.py

# Verify no credentials in staged files
git diff --staged
```

See [SECURITY.md](SECURITY.md) for comprehensive security guidelines.

### Running the Pipeline

**Via Streamlit UI** (Recommended):
```powershell
streamlit run streamlit_app.py
```

Navigate to `http://localhost:8501` in your browser to access the web interface.

**Via Python API**:
```python
from src.pipeline_orchestrator import FinetuningPipeline
from src.configuration_manager import ConfigurationManager
from src.progress_tracker import ProgressTracker

# Initialize components
config_manager = ConfigurationManager()
progress_tracker = ProgressTracker()
pipeline = FinetuningPipeline(config_manager, progress_tracker)

# Run pipeline for a use case
result = pipeline.run("customer_support")
print(f"Final win rate: {result.final_win_rate:.1%}")
print(f"Iterations completed: {result.total_iterations}")
print(f"Improvement: {result.improvement:+.1%}")
```

**Advanced Usage Examples**:

```python
# Resume interrupted pipeline
state_id = "customer_support_20240115_103000"
result = pipeline.resume("customer_support", state_id)

# Run with custom parameters
result = pipeline.run(
    use_case_name="customer_support",
    max_iterations=3,
    performance_threshold=0.70
)

# Access detailed results
for iteration in result.iteration_history:
    print(f"Iteration {iteration.iteration}: {iteration.win_rate:.1%}")
    print(f"  Model: {iteration.endpoint_name}")
    print(f"  Training time: {iteration.training_time_seconds}s")

# Generate performance report
report = progress_tracker.generate_summary_report("customer_support")
print(f"Initial win rate: {report.initial_win_rate:.1%}")
print(f"Final win rate: {report.final_win_rate:.1%}")
print(f"Best iteration: {report.best_iteration}")
```

## Security

**🔒 Protecting Your AWS Credentials**

This project follows AWS security best practices. Your credentials are **never** stored in the project files.

### Quick Security Check

Before pushing to GitHub, run:

```powershell
python scripts/check_security.py
```

This script checks for:
- AWS credentials in files
- Private keys and certificates  
- Sensitive patterns
- Large files
- Unignored sensitive files

### Where Credentials Should Be

✅ **Correct locations:**
- `~/.aws/credentials` (home directory, NOT in project)
- Environment variables (temporary use)
- IAM roles (production on EC2/ECS/Lambda)

❌ **Never store credentials:**
- In project files
- In config files committed to git
- In code files
- In `.env` files (these are gitignored)

### Key Security Files

- **[SECURITY.md](SECURITY.md)** - Comprehensive security guide
- **[.gitignore](.gitignore)** - Excludes sensitive files from git
- **[.env.example](.env.example)** - Template for environment variables
- **[scripts/check_security.py](scripts/check_security.py)** - Security scanner

### Pre-Push Checklist

Before pushing to GitHub:

1. ✅ Run `python scripts/check_security.py`
2. ✅ Review `git diff --staged` for sensitive data
3. ✅ Verify `.env` and credentials are not staged
4. ✅ Check that use case files don't contain sensitive data
5. ✅ Ensure logs are excluded

**See [SECURITY.md](SECURITY.md) and [documentation/GITHUB_PUSH_CHECKLIST.md](documentation/GITHUB_PUSH_CHECKLIST.md) for detailed guidelines and emergency response procedures.**

## Project Structure

```
SageMaker-AI-LLM-Model-Customization-Challenge-Automation/
├── src/                          # Source code
│   ├── configuration_manager.py  # Use case and config management
│   ├── synthetic_data_generator.py  # Training data generation
│   ├── model_trainer.py          # SageMaker training
│   ├── model_deployer.py         # SageMaker deployment
│   ├── inference_engine.py       # Model inference
│   ├── judge.py                  # Response evaluation
│   ├── self_improvement_agent.py # Prompt optimization
│   ├── progress_tracker.py       # State and metrics tracking
│   └── pipeline_orchestrator.py  # Main orchestration
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── property/                 # Property-based tests
│   └── integration/              # Integration tests
├── config/                       # Configuration files
│   ├── pipeline_config.yaml      # Pipeline settings
│   └── use_cases/                # Use case definitions
├── documentation/                # Documentation and guides
│   ├── guides/                   # User-facing guides
│   ├── docs/                     # Technical documentation
│   ├── DIRECTORY_STRUCTURE.md    # Project structure reference
│   ├── GITHUB_PUSH_CHECKLIST.md  # Pre-publication checklist
│   └── SECURITY_QUICK_REFERENCE.md # Security quick reference
├── event_files/                  # Generated data and artifacts
├── progress/                     # Iteration results and state
├── logs/                         # Application logs
├── streamlit_app.py              # Web UI entry point
├── requirements.txt              # Python dependencies
├── SECURITY.md                   # Security best practices
└── README.md                     # This file
```

For detailed directory structure documentation, see [documentation/DIRECTORY_STRUCTURE.md](documentation/DIRECTORY_STRUCTURE.md).

## Use Case Management

### Creating a Use Case

Use cases define the domain, test questions, and evaluation criteria for finetuning.

**Via UI**:
1. Navigate to "Create Use Case" page
2. Fill in all required fields
3. Click "Save Use Case"

**Via YAML**:
Create a file in `config/use_cases/my_use_case.yaml`:

```yaml
name: customer_support
description: |
  Finetune a model to provide helpful, empathetic customer support responses.

test_questions:
  - "My order hasn't arrived. What should I do?"
  - "I was charged twice. How do I get a refund?"

judge_criteria: |
  Evaluate based on helpfulness, empathy, clarity, and completeness.

data_generation_prompt: |
  Generate customer support training examples with excellent service.

judge_prompt: |
  Compare responses based on helpfulness, empathy, and clarity.
```

## Configuration

### Pipeline Configuration

Edit `config/pipeline_config.yaml`:

```yaml
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: my-finetuning-bucket

training:
  base_model: meta-llama/Llama-3.2-3B
  instance_type: ml.g5.2xlarge
  max_training_time_seconds: 86400

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60  # Trigger improvement if win rate < 60%
  max_iterations: 5
  cleanup_resources: true
  artifact_retention_days: 7

retry:
  max_attempts: 3
  initial_backoff_seconds: 2
  max_backoff_seconds: 60
```

### Configuration Parameters Explained

**AWS Settings**:
- `region`: AWS region for all services (SageMaker, Bedrock, S3)
- `bedrock_model_id`: Claude Sonnet 4 model ID for data generation and judging
- `sagemaker_role_arn`: IAM role with SageMaker, S3, and Bedrock permissions
- `s3_bucket`: S3 bucket for storing training data and model artifacts

**Training Settings**:
- `base_model`: Base model to finetune (default: Llama 3.2 3B)
- `instance_type`: SageMaker instance for training (GPU required)
- `max_training_time_seconds`: Maximum training duration (24 hours default)

**Inference Settings**:
- `instance_type`: SageMaker instance for inference endpoints
- `baseline_model_endpoint`: Pre-deployed 70B model endpoint for comparison

**Pipeline Settings**:
- `performance_threshold`: Win rate threshold for triggering self-improvement (0.60 = 60%)
- `max_iterations`: Maximum self-improvement iterations (prevents infinite loops)
- `cleanup_resources`: Auto-delete endpoints after completion (saves costs)
- `artifact_retention_days`: Days to keep training artifacts in S3

**Retry Settings**:
- `max_attempts`: Maximum retry attempts for transient failures
- `initial_backoff_seconds`: Initial retry delay
- `max_backoff_seconds`: Maximum retry delay (exponential backoff cap)

### Environment Variables

You can override configuration with environment variables:

```powershell
# Set AWS region
$env:AWS_REGION = "us-west-2"

# Set AWS profile
$env:AWS_PROFILE = "my-profile"

# Set custom config directory
$env:PIPELINE_CONFIG_DIR = "C:\path\to\configs"
```

## Testing

The project includes comprehensive unit tests, property-based tests, and integration tests.

### Running Tests

```powershell
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/unit/              # Unit tests only
pytest tests/property/          # Property-based tests only
pytest tests/integration/       # Integration tests only

# Run specific test file
pytest tests/unit/test_configuration_manager.py

# Run specific test function
pytest tests/unit/test_configuration_manager.py::test_load_use_case

# Run with coverage report
pytest --cov=src --cov-report=html
# Open htmlcov/index.html to view coverage

# Run with coverage and show missing lines
pytest --cov=src --cov-report=term-missing

# Run tests matching a pattern
pytest -k "configuration"

# Run tests with markers
pytest -m "not integration"  # Skip integration tests
```

### Test Categories

**Unit Tests** (`tests/unit/`):
- Test individual components in isolation
- Use mocked AWS services (via `moto`)
- Fast execution (<1 second per test)
- Focus on specific scenarios and edge cases

**Property-Based Tests** (`tests/property/`):
- Test universal properties across random inputs
- Use `hypothesis` library (100+ examples per test)
- Verify correctness properties from design document
- Catch edge cases that unit tests might miss

**Integration Tests** (`tests/integration/`):
- Test component interactions
- End-to-end pipeline execution with mocked AWS
- Optional AWS integration tests (require credentials)
- Marked with `@pytest.mark.integration`

### Running AWS Integration Tests

AWS integration tests require real AWS credentials and will incur costs:

```powershell
# Run only integration tests
pytest -m integration

# Skip integration tests (default)
pytest -m "not integration"
```

**Note**: Integration tests are optional and primarily used in CI/CD.

### Test Configuration

Configure pytest in `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    integration: marks tests as integration tests (deselect with '-m "not integration"')
    slow: marks tests as slow (deselect with '-m "not slow"')
```

### Writing Tests

When adding new functionality, include:

1. **Unit Tests**: Test specific examples and edge cases
2. **Property-Based Tests**: Test universal properties
3. **Integration Tests**: Test component interactions (if applicable)

Example unit test:
```python
def test_load_use_case():
    """Test loading a use case from configuration"""
    config_manager = ConfigurationManager()
    use_case = config_manager.load_use_case("customer_support")
    assert use_case.name == "customer_support"
    assert len(use_case.test_questions) > 0
```

Example property-based test:
```python
from hypothesis import given, strategies as st

@given(win_rate=st.floats(min_value=0.0, max_value=1.0))
def test_win_rate_calculation(win_rate):
    """Win rate should always be between 0 and 1"""
    assert 0.0 <= win_rate <= 1.0
```

### Test Coverage Goals

- **Overall Coverage**: >80%
- **Critical Components**: >90% (configuration, pipeline orchestrator)
- **Property Tests**: All 41 correctness properties implemented
- **Integration Tests**: All major workflows covered

## Development

### Setting Up Development Environment

See [documentation/guides/SETUP.md](documentation/guides/SETUP.md) for detailed setup instructions.

**Quick Setup**:
```powershell
# Clone repository
git clone https://github.com/yourusername/SageMaker-AI-LLM-Model-Customization-Challenge-Automation.git
cd SageMaker-AI-LLM-Model-Customization-Challenge-Automation

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest hypothesis mypy pylint black

# Run tests to verify setup
pytest
```

### Project Structure Explained

```
SageMaker-AI-LLM-Model-Customization-Challenge-Automation/
├── src/                          # Source code
│   ├── configuration_manager.py  # Use case and config management
│   ├── synthetic_data_generator.py  # Training data generation
│   ├── model_trainer.py          # SageMaker training
│   ├── model_deployer.py         # SageMaker deployment
│   ├── inference_engine.py       # Model inference
│   ├── judge.py                  # Response evaluation
│   ├── self_improvement_agent.py # Prompt optimization
│   ├── progress_tracker.py       # State and metrics tracking
│   └── pipeline_orchestrator.py  # Main orchestration
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests (fast, isolated)
│   ├── property/                 # Property-based tests (hypothesis)
│   ├── integration/              # Integration tests (component interactions)
│   └── fixtures/                 # Test data and mocks
├── config/                       # Configuration files
│   ├── pipeline_config.yaml      # Pipeline settings
│   └── use_cases/                # Use case definitions (YAML)
├── documentation/                # Documentation and guides
│   ├── guides/                   # User-facing setup guides
│   │   └── SETUP.md              # Detailed setup instructions
│   ├── docs/                     # Technical documentation
│   │   ├── implementation/       # Implementation summaries
│   │   ├── AWS_CLIENT_MANAGER.md # AWS client documentation
│   │   ├── LOGGING_GUIDE.md      # Logging best practices
│   │   └── MYPY_GUIDE.md         # Type checking guide
│   ├── DIRECTORY_STRUCTURE.md    # Complete project structure
│   ├── GITHUB_PUSH_CHECKLIST.md  # Pre-publication checklist
│   └── SECURITY_QUICK_REFERENCE.md # Security quick reference
├── event_files/                  # Generated data and artifacts
│   ├── questions/                # Test questions per use case
│   ├── usecases/                 # Use case descriptions
│   ├── judge_prompts/            # Judge prompts per use case
│   └── training_data/            # Generated training data (JSONL)
├── progress/                     # Iteration results and state
│   ├── {use_case}/               # Per-use-case progress
│   │   ├── iteration_N_results.json
│   │   └── pipeline_state_ID.json
│   └── performance_reports/      # Summary reports
├── models/                       # Model artifacts and endpoints
│   └── {use_case}/               # Per-use-case models
│       └── iterN/                # Per-iteration models
├── logs/                         # Application logs
├── streamlit_app.py              # Web UI entry point
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Pytest configuration
├── mypy.ini                      # Type checking configuration
├── .gitignore                    # Git ignore patterns
├── SECURITY.md                   # Security best practices
└── README.md                     # This file
```

For complete directory structure documentation, see [documentation/DIRECTORY_STRUCTURE.md](documentation/DIRECTORY_STRUCTURE.md).

### Development Workflow

1. **Create Feature Branch**
   ```powershell
   git checkout -b feature/my-feature
   ```

2. **Make Changes**
   - Edit source files in `src/`
   - Follow code style guidelines
   - Add type hints and docstrings

3. **Write Tests**
   - Add unit tests in `tests/unit/`
   - Add property tests in `tests/property/` (if applicable)
   - Run tests: `pytest`

4. **Check Code Quality**
   ```powershell
   # Type checking
   mypy src/
   
   # Linting
   pylint src/
   
   # Format code
   black src/ tests/
   ```

5. **Run Full Test Suite**
   ```powershell
   pytest --cov=src --cov-report=term-missing
   ```

6. **Commit and Push**
   ```powershell
   git add .
   git commit -m "Add feature: description"
   git push origin feature/my-feature
   ```

### Code Quality Tools

**Type Checking with mypy**:
```powershell
# Check all source files
mypy src/

# Check specific file
mypy src/configuration_manager.py

# Strict mode
mypy --strict src/
```

**Linting with pylint**:
```powershell
# Lint all source files
pylint src/

# Lint specific file
pylint src/configuration_manager.py

# Generate report
pylint src/ --output-format=text > pylint_report.txt
```

**Code Formatting with black**:
```powershell
# Format all files
black src/ tests/

# Check without modifying
black --check src/

# Show diff
black --diff src/
```

### Adding a New Component

1. **Create Module**: Add new file in `src/`
2. **Define Interface**: Create class with clear methods and docstrings
3. **Add Type Hints**: Annotate all function signatures
4. **Write Unit Tests**: Create `tests/unit/test_<component>.py`
5. **Write Property Tests**: Add to `tests/property/` if applicable
6. **Update Documentation**: Add to README and design.md
7. **Integrate**: Update `pipeline_orchestrator.py` if needed

Example component structure:
```python
"""Module for <component description>."""

from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ComponentConfig:
    """Configuration for component."""
    param1: str
    param2: int

class MyComponent:
    """Component that does X.
    
    This component is responsible for...
    
    Attributes:
        config: Component configuration
        client: AWS client (if applicable)
    """
    
    def __init__(self, config: ComponentConfig):
        """Initialize component.
        
        Args:
            config: Component configuration
        """
        self.config = config
        logger.info(f"Initialized {self.__class__.__name__}")
    
    def do_something(self, input_data: str) -> str:
        """Do something with input data.
        
        Args:
            input_data: Input to process
            
        Returns:
            Processed output
            
        Raises:
            ValueError: If input is invalid
        """
        if not input_data:
            raise ValueError("Input cannot be empty")
        
        # Implementation
        result = input_data.upper()
        logger.debug(f"Processed: {result}")
        return result
```

### Debugging Tips

**Enable Debug Logging**:
```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Use Python Debugger**:
```python
import pdb; pdb.set_trace()  # Set breakpoint
```

**VS Code Debugging**:
Create `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder};${workspaceFolder}/src"
            }
        }
    ]
}
```

**Mock AWS Services**:
```python
from moto import mock_sagemaker, mock_bedrock

@mock_sagemaker
@mock_bedrock
def test_with_mocked_aws():
    # Test code here
    pass
```

### Performance Profiling

**Profile Code Execution**:
```powershell
python -m cProfile -o profile.stats src/pipeline_orchestrator.py
python -m pstats profile.stats
```

**Memory Profiling**:
```powershell
pip install memory_profiler
python -m memory_profiler src/pipeline_orchestrator.py
```

### Continuous Integration

The project uses CI/CD for automated testing:

- **On Pull Request**: Run all tests, linting, type checking
- **On Merge**: Run full test suite including integration tests
- **On Release**: Build and deploy artifacts

### Release Process

1. Update version in `setup.py` or `__version__.py`
2. Update CHANGELOG.md with release notes
3. Create release branch: `git checkout -b release/v1.0.0`
4. Run full test suite: `pytest`
5. Tag release: `git tag -a v1.0.0 -m "Release v1.0.0"`
6. Push tag: `git push origin v1.0.0`
7. Create GitHub release with notes

## Documentation

### User Guides
- **[Main README](README.md)** - Overview, quick start, and comprehensive guide
- **[Setup Guide](documentation/guides/SETUP.md)** - Detailed setup and installation instructions
- **[Security Guide](SECURITY.md)** - Security best practices and credential management
- **[Configuration Guide](config/CONFIGURATION_GUIDE.md)** - Configuration file formats and options

### Technical Documentation
- **[AWS Client Manager](documentation/docs/AWS_CLIENT_MANAGER.md)** - AWS service integration
- **[Logging Guide](documentation/docs/LOGGING_GUIDE.md)** - Logging configuration and best practices
- **[Type Checking Guide](documentation/docs/MYPY_GUIDE.md)** - Type checking with mypy

### Reference Documentation
- **[Directory Structure](documentation/DIRECTORY_STRUCTURE.md)** - Complete project structure
- **[GitHub Push Checklist](documentation/GITHUB_PUSH_CHECKLIST.md)** - Pre-publication checklist
- **[Security Quick Reference](documentation/SECURITY_QUICK_REFERENCE.md)** - Security quick reference card

### Development Documentation
- **[Implementation Summaries](documentation/docs/implementation/)** - Component implementation details
- **[Documentation Index](documentation/README.md)** - Complete documentation index

## AWS Resources

The pipeline creates the following AWS resources:

- **SageMaker Training Jobs**: For model finetuning
- **SageMaker Endpoints**: For model inference
- **S3 Objects**: Training data and model artifacts
- **Bedrock API Calls**: For Claude Sonnet 4 (data generation and judging)

**Cost Considerations**:
- Training: ~$2-5 per training job (ml.g5.2xlarge)
- Inference: ~$1-2 per hour (ml.g5.xlarge endpoint)
- Bedrock: ~$0.003 per 1K input tokens, ~$0.015 per 1K output tokens

Enable `cleanup_resources: true` in config to automatically delete endpoints after pipeline completion.

## Troubleshooting

### Common Issues

#### PowerShell Execution Policy Error

**Issue**: Error when activating virtual environment: "cannot be loaded because running scripts is disabled"

**Solution**: 
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating again: `.\venv\Scripts\Activate.ps1`

---

#### AWS Credentials Not Found

**Issue**: `NoCredentialsError` or `Unable to locate credentials`

**Solutions**:
1. Configure AWS CLI:
   ```powershell
   aws configure
   ```
   Enter your AWS Access Key ID, Secret Access Key, region, and output format.

2. Set environment variables:
   ```powershell
   $env:AWS_ACCESS_KEY_ID = "your-access-key"
   $env:AWS_SECRET_ACCESS_KEY = "your-secret-key"
   $env:AWS_REGION = "us-east-1"
   ```

3. Use AWS profile:
   ```powershell
   $env:AWS_PROFILE = "my-profile"
   ```

---

#### SageMaker Training Job Fails

**Issue**: Training job fails with error in CloudWatch logs

**Solutions**:

1. **Check IAM Permissions**: Ensure SageMaker role has:
   - `AmazonSageMakerFullAccess`
   - `AmazonS3FullAccess` (or specific bucket access)
   - `AmazonBedrockFullAccess`

2. **Check Instance Quotas**: Verify you have quota for `ml.g5.2xlarge` instances:
   - Go to AWS Service Quotas console
   - Search for "SageMaker"
   - Check "ml.g5.2xlarge for training job usage"

3. **Check Training Data**: Ensure JSONL format is valid:
   ```powershell
   python -c "import json; [json.loads(line) for line in open('training_data.jsonl')]"
   ```

4. **Review CloudWatch Logs**:
   - Go to CloudWatch console
   - Navigate to Log Groups → `/aws/sagemaker/TrainingJobs`
   - Find your job and review error messages

---

#### Bedrock API Rate Limit Errors

**Issue**: `ThrottlingException` or rate limit errors from Bedrock

**Solutions**:

1. **Automatic Retry**: Pipeline automatically retries with exponential backoff
2. **Reduce Batch Size**: Lower `batch_size` in data generation
3. **Request Quota Increase**: Contact AWS support for higher Bedrock quotas
4. **Add Delays**: Increase `initial_backoff_seconds` in config

---

#### Model Deployment Timeout

**Issue**: Endpoint deployment takes too long or times out

**Solutions**:

1. **Wait Longer**: Deployment can take 5-10 minutes, be patient
2. **Check Endpoint Status**:
   ```python
   import boto3
   client = boto3.client('sagemaker')
   response = client.describe_endpoint(EndpointName='your-endpoint')
   print(response['EndpointStatus'])
   ```
3. **Check Instance Availability**: Ensure `ml.g5.xlarge` instances are available in your region
4. **Review CloudWatch Logs**: Check for deployment errors

---

#### Low Win Rate / Poor Performance

**Issue**: Finetuned model consistently loses to baseline

**Solutions**:

1. **Let Self-Improvement Run**: Pipeline automatically optimizes prompts after low win rate
2. **Review Training Data**: Check if generated data matches use case
3. **Adjust Judge Criteria**: Ensure criteria align with desired behavior
4. **Increase Training Data**: Generate more examples (1000+ recommended)
5. **Review Test Questions**: Ensure questions are representative of use case

---

#### Streamlit UI Not Loading

**Issue**: `streamlit run streamlit_app.py` fails or UI doesn't load

**Solutions**:

1. **Check Dependencies**:
   ```powershell
   pip install streamlit pandas plotly
   ```

2. **Check Port Availability**: Default port 8501 might be in use
   ```powershell
   streamlit run streamlit_app.py --server.port 8502
   ```

3. **Clear Cache**:
   ```powershell
   streamlit cache clear
   ```

4. **Check Browser**: Try different browser or incognito mode

---

#### Import Errors

**Issue**: `ModuleNotFoundError` when running scripts

**Solutions**:

1. **Activate Virtual Environment**:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Set PYTHONPATH**:
   ```powershell
   $env:PYTHONPATH = "$PWD;$PWD\src"
   ```

4. **Verify Installation**:
   ```powershell
   pip list | Select-String "boto3"
   ```

---

#### Out of Memory Errors

**Issue**: Training or inference fails with OOM errors

**Solutions**:

1. **Reduce Batch Size**: Lower batch size in training config
2. **Use Larger Instance**: Upgrade to `ml.g5.4xlarge` or larger
3. **Reduce Dataset Size**: Start with smaller dataset for testing
4. **Enable Gradient Checkpointing**: Add to training hyperparameters

---

#### Configuration Validation Errors

**Issue**: Pipeline fails with "Invalid configuration" error

**Solutions**:

1. **Check Required Fields**: Ensure all required fields are present in YAML
2. **Validate YAML Syntax**:
   ```python
   import yaml
   with open('config/pipeline_config.yaml') as f:
       config = yaml.safe_load(f)
   ```
3. **Check Data Types**: Ensure numbers are not quoted, booleans are lowercase
4. **Review Error Message**: Error message specifies which field is invalid

---

### Getting More Help

If you're still experiencing issues:

1. **Check Logs**: Review logs in `logs/` directory for detailed error messages
2. **Enable Debug Logging**: Set `LOG_LEVEL=DEBUG` environment variable
3. **Check AWS Console**: Review SageMaker, S3, and CloudWatch for resource status
4. **Search Issues**: Check GitHub issues for similar problems
5. **Open Issue**: Create new GitHub issue with:
   - Error message and stack trace
   - Python version and OS
   - AWS region and services used
   - Steps to reproduce
   - Relevant log excerpts

### Debug Mode

Enable debug logging for more detailed output:

```powershell
$env:LOG_LEVEL = "DEBUG"
python -m src.pipeline_orchestrator
```

Or in code:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Useful AWS CLI Commands

```powershell
# List SageMaker endpoints
aws sagemaker list-endpoints

# Describe endpoint
aws sagemaker describe-endpoint --endpoint-name my-endpoint

# List training jobs
aws sagemaker list-training-jobs

# Check S3 bucket contents
aws s3 ls s3://my-finetuning-bucket/

# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

## Frequently Asked Questions (FAQ)

### General Questions

**Q: What models can I finetune with this pipeline?**
A: Currently supports Llama 3.2 3B by default. The architecture is extensible to support other models available through SageMaker JumpStart.

**Q: How much does it cost to run the pipeline?**
A: Approximate costs per run:
- Training: $2-5 (ml.g5.2xlarge, ~1-2 hours)
- Inference endpoint: $1-2/hour (ml.g5.xlarge)
- Bedrock API: $0.003/1K input tokens, $0.015/1K output tokens
- Total per iteration: ~$10-20 depending on dataset size

Enable `cleanup_resources: true` to minimize costs.

**Q: How long does a complete pipeline run take?**
A: Typical timeline:
- Data generation: 10-30 minutes (1000 examples)
- Training: 1-2 hours
- Deployment: 5-10 minutes
- Evaluation: 10-20 minutes
- Total: 2-3 hours per iteration

**Q: Can I run this locally without AWS?**
A: No, the pipeline requires AWS services (SageMaker, Bedrock, S3). However, you can run tests locally with mocked AWS services.

**Q: What's the minimum dataset size for good results?**
A: Recommended minimum: 500-1000 training examples. Larger datasets (2000+) generally produce better results.

### Technical Questions

**Q: Why does the finetuned model lose to the baseline?**
A: Common reasons:
- Insufficient training data
- Training data doesn't match test questions
- Judge criteria not aligned with desired behavior
- Need more training epochs

Let the self-improvement loop run to automatically optimize prompts.

**Q: Can I use a different judge model?**
A: Yes, the Judge component is modular. You can implement a custom judge by extending the `Judge` class.

**Q: How do I add support for a new base model?**
A: Update `ModelTrainer` to use the new model ID and adjust hyperparameters. Ensure the model is available in SageMaker JumpStart.

**Q: Can I run multiple pipelines in parallel?**
A: Yes, but be mindful of AWS quotas (concurrent training jobs, endpoints, Bedrock rate limits).

**Q: How do I export results for analysis?**
A: Results are stored in JSON format in `progress/`. Use the Streamlit UI export feature or read JSON files directly.

### Troubleshooting Questions

**Q: Training job fails immediately - what should I check?**
A: Check:
1. IAM role permissions
2. Training data format (valid JSONL)
3. S3 bucket access
4. Instance quotas in your region

**Q: Endpoint deployment stuck "Creating" - what to do?**
A: Wait 10-15 minutes. If still stuck, check:
1. Instance availability in your region
2. CloudWatch logs for errors
3. SageMaker quotas

**Q: How do I resume a failed pipeline?**
A: Use `pipeline.resume(use_case_name, state_id)`. State ID is logged when pipeline saves progress.

**Q: Can I modify prompts during a run?**
A: No, prompts are fixed per iteration. You can manually edit use case config and start a new run.

### Best Practices Questions

**Q: How many iterations should I run?**
A: Default is 5. Most use cases converge in 2-3 iterations. If not improving after 3 iterations, review use case definition.

**Q: What's a good performance threshold?**
A: 60% is a good starting point. Adjust based on your use case:
- Simple tasks: 70-80%
- Complex tasks: 50-60%

**Q: Should I use cleanup_resources?**
A: Yes for development/testing to save costs. No for production if you need persistent endpoints.

**Q: How do I version control use cases?**
A: Use case configs are YAML files in `config/use_cases/`. Commit them to git. The system also maintains version history automatically.

**Q: Can I use this for production workloads?**
A: The pipeline is designed for experimentation and development. For production:
- Add authentication/authorization
- Implement monitoring and alerting
- Set up automated backups
- Review and harden security settings

## Contributing

We welcome contributions to the Automated LLM Finetuning Pipeline! Whether you're fixing bugs, adding features, improving documentation, or suggesting enhancements, your help is appreciated.

### How to Contribute

1. **Fork the Repository**
   - Click the "Fork" button on GitHub
   - Clone your fork locally: `git clone <your-fork-url>`

2. **Set Up Development Environment**
   - Follow the [documentation/guides/SETUP.md](documentation/guides/SETUP.md) guide
   - Install development dependencies: `pip install -r requirements.txt`
   - Configure pre-commit hooks (if available)

3. **Create a Feature Branch**
   ```powershell
   git checkout -b feature/your-feature-name
   ```
   Use descriptive branch names:
   - `feature/add-new-model-support`
   - `bugfix/fix-retry-logic`
   - `docs/improve-setup-guide`

4. **Make Your Changes**
   - Write clean, well-documented code
   - Follow existing code style and conventions
   - Add type hints to all functions
   - Update docstrings for modified functions

5. **Add Tests**
   - Write unit tests for new functionality
   - Add property-based tests for universal properties
   - Ensure all tests pass: `pytest`
   - Maintain or improve code coverage: `pytest --cov=src`

6. **Update Documentation**
   - Update README.md if adding new features
   - Update documentation/guides/SETUP.md if changing setup process
   - Add docstrings to new classes and functions
   - Update design documentation for architectural changes

7. **Run Quality Checks**
   ```powershell
   # Type checking
   mypy src/
   
   # Linting
   pylint src/
   
   # Format code
   black src/ tests/
   
   # Run all tests
   pytest
   ```

8. **Commit Your Changes**
   - Write clear, descriptive commit messages
   - Reference issue numbers if applicable
   ```powershell
   git add .
   git commit -m "Add support for custom base models (#123)"
   ```

9. **Push and Create Pull Request**
   ```powershell
   git push origin feature/your-feature-name
   ```
   - Open a pull request on GitHub
   - Provide a clear description of changes
   - Link related issues
   - Wait for review and address feedback

### Code Style Guidelines

- **Python Version**: Target Python 3.10+
- **Formatting**: Use `black` with default settings
- **Imports**: Group imports (standard library, third-party, local)
- **Type Hints**: Add type hints to all function signatures
- **Docstrings**: Use Google-style docstrings
- **Line Length**: Maximum 100 characters (black default)
- **Naming Conventions**:
  - Classes: `PascalCase`
  - Functions/methods: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
  - Private members: `_leading_underscore`

### Testing Guidelines

- **Test Coverage**: Aim for >80% coverage
- **Test Types**:
  - Unit tests for individual components
  - Property-based tests for universal properties
  - Integration tests for component interactions
- **Test Naming**: `test_<function_name>_<scenario>`
- **Mocking**: Use `moto` for AWS services, avoid over-mocking
- **Fixtures**: Place reusable fixtures in `tests/fixtures/`

### Documentation Guidelines

- **README**: Keep high-level, user-focused
- **documentation/guides/SETUP.md**: Detailed setup instructions
- **Code Comments**: Explain "why", not "what"
- **Docstrings**: Document parameters, return values, exceptions
- **Examples**: Include usage examples in docstrings

### Reporting Issues

When reporting bugs or requesting features:

1. **Search Existing Issues**: Check if already reported
2. **Use Issue Templates**: Fill out all sections
3. **Provide Context**:
   - Python version
   - Operating system
   - AWS region and services used
   - Error messages and stack traces
   - Steps to reproduce
4. **Be Specific**: Clear, concise descriptions help us help you

### Pull Request Review Process

1. **Automated Checks**: CI/CD runs tests and linting
2. **Code Review**: Maintainers review code quality and design
3. **Feedback**: Address review comments and suggestions
4. **Approval**: At least one maintainer approval required
5. **Merge**: Maintainers merge approved PRs

### Areas for Contribution

We especially welcome contributions in these areas:

- **New Model Support**: Add support for additional base models
- **Alternative Judges**: Implement alternative evaluation methods
- **UI Enhancements**: Improve Streamlit interface
- **Performance Optimization**: Speed up data generation or inference
- **Documentation**: Improve guides, add tutorials, fix typos
- **Testing**: Increase test coverage, add edge cases
- **Bug Fixes**: Fix reported issues
- **Examples**: Add example use cases and tutorials

### Questions?

- **General Questions**: Open a GitHub Discussion
- **Bug Reports**: Open a GitHub Issue
- **Security Issues**: Email maintainers directly (see SECURITY.md if available)
- **Feature Requests**: Open a GitHub Issue with "enhancement" label

### Code of Conduct

Be respectful, inclusive, and professional in all interactions. We're building this together!

Thank you for contributing to the Automated LLM Finetuning Pipeline! 🚀

## License

[Add license information]

## Acknowledgments

This pipeline builds upon proven patterns from production manual finetuning workflows, documented in `.kiro/specs/llm-finetuning-pipeline-best-practices/requirements.md`.

---

**Status**: In Development
**Python Version**: 3.10+
**AWS Services**: SageMaker, Bedrock, S3
