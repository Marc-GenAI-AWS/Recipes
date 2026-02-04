# Configuration Directory

This directory contains configuration files for the automated LLM finetuning pipeline.

## Quick Start

**New to the pipeline?** Start here:
1. Read [QUICK_START.md](QUICK_START.md) for a 5-minute setup guide
2. Copy `pipeline_config.dev.yaml` and update AWS settings
3. Copy `use_cases/template.yaml` to create your first use case
4. Run validation: `python -m src.configuration_manager validate-all`

## Documentation

- **[QUICK_START.md](QUICK_START.md)**: 5-minute setup guide with examples
- **[CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md)**: Comprehensive configuration reference
- **Design Document**: `.kiro/specs/automated-llm-finetuning-pipeline/design.md`

## Directory Structure

```
config/
├── README.md                          # This file
├── QUICK_START.md                     # Quick setup guide
├── CONFIGURATION_GUIDE.md             # Detailed configuration reference
├── pipeline_config.dev.yaml           # Development environment template
├── pipeline_config.prod.yaml          # Production environment template
└── use_cases/                         # Use case definitions
    ├── template.yaml                  # Blank template for new use cases
    ├── customer_support.example.yaml  # Example: Customer support
    └── code_review.example.yaml       # Example: Code review
```

## Configuration Files

### Pipeline Configuration

**Templates**:
- `pipeline_config.dev.yaml`: Development environment (small datasets, low cost, fast iteration)
- `pipeline_config.prod.yaml`: Production environment (large datasets, high quality, monitoring)

**Key Settings**:
- AWS region, credentials, and S3 bucket
- Model IDs for Claude Sonnet 4 and Llama models
- SageMaker role ARN and instance types
- Training and inference parameters
- Performance thresholds and iteration limits
- Resource cleanup and retention policies
- Logging and monitoring configuration

**Usage**:
```bash
# Copy and customize for your environment
cp pipeline_config.dev.yaml pipeline_config.yaml

# Edit AWS settings
vim pipeline_config.yaml

# Validate
python -m src.configuration_manager validate pipeline_config.yaml
```

### Use Case Configuration

**Templates**:
- `use_cases/template.yaml`: Blank template with instructions
- `use_cases/customer_support.example.yaml`: Complete customer support example
- `use_cases/code_review.example.yaml`: Complete code review example

**Required Fields**:
- `name`: Unique identifier (lowercase with underscores)
- `description`: Detailed description of desired model behavior
- `test_questions`: List of evaluation questions (minimum 5)
- `judge_criteria`: Criteria for evaluating response quality
- `data_generation_prompt`: Instructions for generating training data
- `judge_prompt`: Instructions for comparing responses

**Optional Fields**:
- `custom_config`: Override pipeline settings for this use case

**Usage**:
```bash
# Create new use case from template
cp use_cases/template.yaml use_cases/my_use_case.yaml

# Edit use case definition
vim use_cases/my_use_case.yaml

# Validate
python -m src.configuration_manager validate use_cases/my_use_case.yaml
```

## Environment Selection

Choose the appropriate configuration for your needs:

### Development Environment
**Use when**: Testing, debugging, experimenting with prompts

**Characteristics**:
- Small datasets (500 examples)
- Small instances (ml.g5.xlarge)
- Few iterations (3 max)
- Auto cleanup enabled
- Verbose logging
- **Cost**: ~$5-10 per run

### Production Environment
**Use when**: Deploying models for real use, achieving best quality

**Characteristics**:
- Large datasets (2000+ examples)
- Large instances (ml.g5.2xlarge)
- More iterations (5 max)
- Auto cleanup disabled
- Monitoring and alerting
- **Cost**: ~$50-100 per run

## Common Tasks

### Create a New Use Case

```bash
# 1. Copy template
cp use_cases/template.yaml use_cases/my_use_case.yaml

# 2. Edit configuration
vim use_cases/my_use_case.yaml

# 3. Validate
python -m src.configuration_manager validate use_cases/my_use_case.yaml

# 4. Run pipeline
python -m src.pipeline run my_use_case
```

### Switch Environments

```bash
# Use development configuration
export PIPELINE_CONFIG=config/pipeline_config.dev.yaml

# Use production configuration
export PIPELINE_CONFIG=config/pipeline_config.prod.yaml
```

### Validate All Configurations

```bash
python -m src.configuration_manager validate-all
```

### List Available Use Cases

```bash
python -m src.configuration_manager list-use-cases
```

## Examples

### Minimal Use Case

```yaml
name: simple_qa
description: Answer questions clearly and accurately
test_questions:
  - "What is Python?"
  - "How does machine learning work?"
  - "Explain APIs simply."
judge_criteria: Clarity, accuracy, helpfulness
data_generation_prompt: Generate Q&A pairs about technology
judge_prompt: Choose the clearer, more accurate response
```

### Custom Configuration Override

```yaml
name: specialized_use_case
description: High-quality specialized model
# ... other fields ...
custom_config:
  num_examples: 3000      # More training data
  training_epochs: 7      # More training
  performance_threshold: 0.70  # Higher bar
```

## Validation

All configurations are validated before use. Common validation checks:

- Required fields are present
- AWS ARNs are properly formatted
- Thresholds are in valid ranges (0.0-1.0)
- Test questions list is non-empty
- Prompts are non-empty strings
- Instance types are valid SageMaker instances

Run validation:
```bash
# Validate specific file
python -m src.configuration_manager validate config/pipeline_config.yaml

# Validate all configurations
python -m src.configuration_manager validate-all
```

## Best Practices

1. **Version Control**: Keep configurations in git
2. **Environment Separation**: Use separate configs for dev/prod
3. **Start Small**: Begin with small datasets in development
4. **Validate Early**: Always validate before running pipeline
5. **Document Changes**: Add comments explaining custom settings
6. **Monitor Costs**: Set up AWS billing alerts
7. **Clean Up**: Delete unused endpoints to save costs
8. **Iterate**: Refine prompts based on results

## Troubleshooting

### Configuration Validation Fails

```bash
# Run with verbose output
python -m src.configuration_manager validate --verbose your_config.yaml
```

### AWS Access Issues

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check SageMaker role
aws iam get-role --role-name SageMakerFinetuningRole

# Verify S3 bucket
aws s3 ls s3://your-bucket
```

### Need Help?

- See [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) for detailed documentation
- See [QUICK_START.md](QUICK_START.md) for setup instructions
- Check the design document for architecture details
- Review example use cases for reference

## Additional Resources

- [AWS SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Design Document](../.kiro/specs/automated-llm-finetuning-pipeline/design.md)
- [Requirements Document](../.kiro/specs/automated-llm-finetuning-pipeline/requirements.md)
