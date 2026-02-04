# Configuration Guide

This guide explains how to configure the automated LLM finetuning pipeline for your use cases.

## Table of Contents

1. [Overview](#overview)
2. [Pipeline Configuration](#pipeline-configuration)
3. [Use Case Configuration](#use-case-configuration)
4. [Environment-Specific Settings](#environment-specific-settings)
5. [AWS Setup](#aws-setup)
6. [Configuration Validation](#configuration-validation)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Overview

The pipeline uses YAML configuration files to manage:

- **Pipeline Configuration**: AWS settings, model IDs, training parameters, thresholds
- **Use Case Configuration**: Domain-specific settings, test questions, prompts

### Configuration Files

```
config/
├── pipeline_config.dev.yaml      # Development environment
├── pipeline_config.prod.yaml     # Production environment
├── use_cases/                    # Use case definitions
│   ├── customer_support.example.yaml
│   ├── code_review.example.yaml
│   └── your_use_case.yaml
└── CONFIGURATION_GUIDE.md        # This file
```

## Pipeline Configuration

### Selecting Configuration File

Set the environment variable to choose which configuration to use:

```bash
# Development
export PIPELINE_CONFIG=config/pipeline_config.dev.yaml

# Production
export PIPELINE_CONFIG=config/pipeline_config.prod.yaml
```

Or specify in code:

```python
from src.configuration_manager import ConfigurationManager

config_manager = ConfigurationManager(
    config_file="config/pipeline_config.prod.yaml"
)
```

### Key Configuration Sections

#### 1. AWS Configuration

```yaml
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerRole
  s3_bucket: your-finetuning-bucket
  s3_prefix: prod/finetuning-pipeline
```

**Required Settings**:
- `region`: AWS region for all services (must support Bedrock and SageMaker)
- `bedrock_model_id`: Claude Sonnet 4 model ID for data generation and judging
- `sagemaker_role_arn`: IAM role with permissions for SageMaker, S3, CloudWatch
- `s3_bucket`: S3 bucket for storing data and artifacts
- `s3_prefix`: Prefix for organizing files within the bucket

**Setup Instructions**:
1. Create an S3 bucket in your chosen region
2. Create a SageMaker execution role (see [AWS Setup](#aws-setup))
3. Ensure Bedrock access is enabled in your region
4. Update the configuration with your values

#### 2. Training Configuration

```yaml
training:
  base_model: meta-llama/Llama-3.2-3B
  instance_type: ml.g5.2xlarge
  max_training_time_seconds: 21600
  volume_size_gb: 100
  lora_config:
    r: 16
    lora_alpha: 32
    target_modules: ["q_proj", "v_proj", "k_proj", "o_proj"]
    lora_dropout: 0.05
  default_hyperparameters:
    epochs: 5
    learning_rate: 0.0001
    batch_size: 8
    warmup_steps: 50
```

**Key Parameters**:
- `instance_type`: SageMaker instance for training
  - Dev: `ml.g5.xlarge` (cheaper, slower)
  - Prod: `ml.g5.2xlarge` or larger (faster, better quality)
- `max_training_time_seconds`: Maximum training duration
  - Dev: 3600 (1 hour)
  - Prod: 21600 (6 hours)
- `lora_config.r`: LoRA rank (higher = more parameters, better quality)
  - Dev: 8
  - Prod: 16-32
- `default_hyperparameters`: Can be overridden by dataset analysis

**Cost Considerations**:
- `ml.g5.xlarge`: ~$1.50/hour
- `ml.g5.2xlarge`: ~$2.50/hour
- Training typically takes 1-4 hours depending on dataset size

#### 3. Inference Configuration

```yaml
inference:
  instance_type: ml.g5.2xlarge
  initial_instance_count: 2
  baseline_model_endpoint: llama-70b-baseline-prod
  max_new_tokens: 1024
  temperature: 0.7
  top_p: 0.9
```

**Key Parameters**:
- `instance_type`: SageMaker instance for inference
- `initial_instance_count`: Number of instances (use 2+ for production)
- `baseline_model_endpoint`: Pre-deployed 70B model endpoint name
- `max_new_tokens`: Maximum response length
- `temperature`: Sampling temperature (0.0-1.0, higher = more creative)
- `top_p`: Nucleus sampling parameter

**Prerequisites**:
- You must deploy a baseline 70B model endpoint before running the pipeline
- The endpoint name must match the configuration

#### 4. Pipeline Configuration

```yaml
pipeline:
  performance_threshold: 0.60
  max_iterations: 5
  cleanup_resources: false
  artifact_retention_days: 30
  verbose_logging: false
```

**Key Parameters**:
- `performance_threshold`: Minimum win rate (0.0-1.0)
  - Below this triggers self-improvement
  - Typical: 0.60 (60% win rate)
- `max_iterations`: Maximum self-improvement cycles
  - Dev: 3 (save costs)
  - Prod: 5 (better results)
- `cleanup_resources`: Auto-delete endpoints after completion
  - Dev: `true` (save costs)
  - Prod: `false` (preserve for review)
- `artifact_retention_days`: How long to keep training artifacts
  - Dev: 3 days
  - Prod: 30 days

#### 5. Data Generation Configuration

```yaml
data_generation:
  num_examples: 2000
  batch_size: 50
  enable_unicode_cleaning: true
  enable_deduplication: true
  quality_validation:
    enabled: true
    min_instruction_length: 10
    min_response_length: 20
```

**Key Parameters**:
- `num_examples`: Number of training examples to generate
  - Dev: 500 (faster, cheaper)
  - Prod: 2000+ (better quality)
- `batch_size`: Examples per API call
  - Larger = faster but more memory
  - Typical: 25-50
- `quality_validation`: Filters out low-quality examples

**Cost Considerations**:
- Claude Sonnet 4 pricing: ~$3 per million input tokens, ~$15 per million output tokens
- 2000 examples ≈ $5-10 depending on complexity

#### 6. Retry Configuration

```yaml
retry:
  max_attempts: 5
  initial_backoff_seconds: 2
  max_backoff_seconds: 60
  jitter_factor: 0.2
```

**Key Parameters**:
- `max_attempts`: Number of retries for transient errors
  - Dev: 3 (fail faster)
  - Prod: 5 (more resilient)
- `initial_backoff_seconds`: Starting delay
- `max_backoff_seconds`: Maximum delay between retries
- `jitter_factor`: Randomization to avoid thundering herd

#### 7. Logging Configuration

```yaml
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  structured: true
  file_path: logs/pipeline_prod.log
  console_enabled: true
```

**Log Levels**:
- `DEBUG`: Verbose, for development
- `INFO`: Standard, for production
- `WARNING`: Only warnings and errors
- `ERROR`: Only errors

#### 8. Monitoring Configuration

```yaml
monitoring:
  cloudwatch_enabled: true
  metrics_namespace: FinetuningPipeline/Prod
  track_performance: true
  alerting:
    enabled: true
    sns_topic_arn: arn:aws:sns:us-east-1:123456789012:alerts
    alert_on_failure: true
    alert_on_low_win_rate: true
```

**Production Features**:
- CloudWatch metrics for tracking
- SNS alerts for failures
- Performance tracking across iterations

## Use Case Configuration

### Creating a New Use Case

1. Copy an example template:
   ```bash
   cp config/use_cases/customer_support.example.yaml \
      config/use_cases/my_use_case.yaml
   ```

2. Edit the configuration:
   ```yaml
   name: my_use_case  # Unique identifier
   description: |
     Detailed description of what the model should do
   test_questions:
     - "Question 1"
     - "Question 2"
   judge_criteria: |
     How to evaluate responses
   data_generation_prompt: |
     How to generate training data
   judge_prompt: |
     How to compare responses
   ```

3. Validate the configuration:
   ```bash
   python -m src.configuration_manager validate config/use_cases/my_use_case.yaml
   ```

### Use Case Fields

#### Required Fields

1. **name** (string)
   - Unique identifier for the use case
   - Use lowercase with underscores
   - Example: `customer_support`, `code_review`

2. **description** (string)
   - Detailed description of the use case
   - Explain desired model behavior
   - Include target domains or scenarios

3. **test_questions** (list of strings)
   - Questions for evaluating model performance
   - Should be realistic and representative
   - Minimum: 5 questions
   - Recommended: 10-20 questions
   - Cover diverse scenarios within the domain

4. **judge_criteria** (string)
   - Criteria for evaluating response quality
   - Should be specific and measurable
   - Include weights if applicable
   - Guide the judge on what matters most

5. **data_generation_prompt** (string)
   - Instructions for generating training data
   - Explain desired format and quality
   - Provide guidelines for variety
   - Include example format

6. **judge_prompt** (string)
   - Instructions for comparing responses
   - Explain evaluation process
   - Specify output format
   - Emphasize objectivity

#### Optional Fields

7. **custom_config** (object)
   - Override pipeline settings for this use case
   - Example:
     ```yaml
     custom_config:
       num_examples: 1500
       training_epochs: 4
       performance_threshold: 0.65
     ```

8. **metadata** (object)
   - Automatically managed by the system
   - Includes version, timestamps
   - Don't edit manually

### Writing Effective Prompts

#### Data Generation Prompt Best Practices

1. **Be Specific**: Clearly describe what kind of examples to generate
2. **Provide Structure**: Specify the exact JSON format required
3. **Encourage Variety**: Ask for diverse scenarios and complexity levels
4. **Set Quality Standards**: Define what makes a good example
5. **Include Examples**: Show the desired format

Example:
```yaml
data_generation_prompt: |
  Generate training examples for [domain].
  
  Each example should include:
  - instruction: [what to include]
  - context: [what to include]
  - response: [what to include]
  
  Guidelines:
  1. Variety: Cover [scenarios]
  2. Quality: Ensure [standards]
  3. Format: Use this JSON structure:
     ```json
     {
       "instruction": "...",
       "context": "...",
       "response": "..."
     }
     ```
```

#### Judge Prompt Best Practices

1. **Define Criteria**: List specific evaluation criteria
2. **Provide Process**: Explain step-by-step evaluation
3. **Specify Format**: Require structured JSON output
4. **Emphasize Objectivity**: Remind to be fair and thorough

Example:
```yaml
judge_prompt: |
  Compare Response A and Response B for the given question.
  
  Evaluation Criteria:
  1. [Criterion 1] - [description]
  2. [Criterion 2] - [description]
  
  Process:
  1. Read the question carefully
  2. Evaluate each response on the criteria
  3. Determine which is superior overall
  
  Output Format:
  ```json
  {
    "winner": "A" or "B" or "tie",
    "reasoning": "Detailed explanation",
    "confidence": 0.0 to 1.0
  }
  ```
```

### Test Questions Guidelines

1. **Representativeness**: Cover the full range of scenarios
2. **Realism**: Use authentic, natural language
3. **Difficulty**: Include easy, medium, and hard questions
4. **Clarity**: Make questions unambiguous
5. **Diversity**: Vary question types and complexity

Example:
```yaml
test_questions:
  # Simple, common scenario
  - "How do I reset my password?"
  
  # Medium complexity with context
  - "I tried to reset my password but didn't receive the email. What should I do?"
  
  # Complex, multi-part question
  - "My account was locked after failed login attempts, and now I can't access the password reset page. How can I regain access?"
  
  # Edge case
  - "I deleted my account but want to reactivate it. Is that possible?"
```

## Environment-Specific Settings

### Development Environment

**Optimized for**: Fast iteration, low cost, debugging

Key settings:
- Smaller datasets (500 examples)
- Smaller instances (ml.g5.xlarge)
- Fewer iterations (3 max)
- Shorter retention (3 days)
- Auto cleanup enabled
- Verbose logging (DEBUG)
- CloudWatch disabled

**Use when**:
- Testing new use cases
- Debugging pipeline issues
- Experimenting with prompts
- Learning the system

### Production Environment

**Optimized for**: Quality, reliability, monitoring

Key settings:
- Larger datasets (2000+ examples)
- Larger instances (ml.g5.2xlarge)
- More iterations (5 max)
- Longer retention (30 days)
- Auto cleanup disabled
- Standard logging (INFO)
- CloudWatch enabled
- Alerting enabled

**Use when**:
- Deploying models for real use
- Achieving best quality
- Requiring monitoring and alerts
- Need for audit trails

### Creating Custom Environments

You can create custom configurations for specific needs:

```bash
cp config/pipeline_config.prod.yaml config/pipeline_config.staging.yaml
# Edit staging-specific settings
```

## AWS Setup

### Prerequisites

1. **AWS Account** with access to:
   - Amazon SageMaker
   - Amazon Bedrock (Claude Sonnet 4)
   - Amazon S3
   - Amazon CloudWatch (optional)
   - Amazon SNS (optional, for alerts)

2. **AWS CLI** configured with credentials:
   ```bash
   aws configure
   ```

### Step 1: Create S3 Bucket

```bash
# Create bucket
aws s3 mb s3://your-finetuning-bucket --region us-east-1

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket your-finetuning-bucket \
  --versioning-configuration Status=Enabled

# Enable encryption (recommended)
aws s3api put-bucket-encryption \
  --bucket your-finetuning-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### Step 2: Create IAM Role for SageMaker

Create a file `sagemaker-trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sagemaker.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Create the role:
```bash
aws iam create-role \
  --role-name SageMakerFinetuningRole \
  --assume-role-policy-document file://sagemaker-trust-policy.json
```

Attach policies:
```bash
# SageMaker full access
aws iam attach-role-policy \
  --role-name SageMakerFinetuningRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

# S3 access
aws iam attach-role-policy \
  --role-name SageMakerFinetuningRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# CloudWatch access
aws iam attach-role-policy \
  --role-name SageMakerFinetuningRole \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchFullAccess
```

Get the role ARN:
```bash
aws iam get-role --role-name SageMakerFinetuningRole --query 'Role.Arn' --output text
```

Update your configuration with this ARN.

### Step 3: Enable Bedrock Access

1. Go to AWS Console → Bedrock
2. Navigate to "Model access"
3. Request access to "Claude Sonnet 4"
4. Wait for approval (usually instant)

### Step 4: Deploy Baseline Model

You need a baseline 70B model endpoint for comparison:

```python
from sagemaker.jumpstart.model import JumpStartModel

# Deploy Llama 3.1 70B as baseline
baseline_model = JumpStartModel(
    model_id="meta-textgeneration-llama-3-1-70b",
    role="arn:aws:iam::YOUR_ACCOUNT:role/SageMakerFinetuningRole"
)

baseline_predictor = baseline_model.deploy(
    instance_type="ml.g5.12xlarge",
    initial_instance_count=1,
    endpoint_name="llama-70b-baseline-prod"
)
```

**Note**: This is expensive (~$7/hour). Consider:
- Using a smaller baseline model for development
- Sharing one baseline endpoint across use cases
- Deleting when not in use

### Step 5: Set Up Monitoring (Optional)

Create SNS topic for alerts:
```bash
aws sns create-topic --name finetuning-alerts

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT:finetuning-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

Update configuration with the topic ARN.

## Configuration Validation

### Validating Configuration Files

Use the built-in validation tool:

```bash
# Validate pipeline configuration
python -m src.configuration_manager validate config/pipeline_config.prod.yaml

# Validate use case configuration
python -m src.configuration_manager validate config/use_cases/customer_support.yaml

# Validate all configurations
python -m src.configuration_manager validate-all
```

### Common Validation Errors

1. **Missing Required Fields**
   ```
   Error: Use case 'my_use_case' is missing required field: 'judge_criteria'
   ```
   Solution: Add the missing field to your configuration

2. **Invalid AWS ARN**
   ```
   Error: Invalid SageMaker role ARN format
   ```
   Solution: Ensure ARN follows format: `arn:aws:iam::ACCOUNT:role/ROLE_NAME`

3. **Invalid Threshold**
   ```
   Error: performance_threshold must be between 0.0 and 1.0
   ```
   Solution: Use a decimal value like 0.60 for 60%

4. **Empty Test Questions**
   ```
   Error: test_questions must contain at least 1 question
   ```
   Solution: Add test questions to your use case

### Manual Validation Checklist

Before running the pipeline, verify:

- [ ] AWS credentials are configured (`aws sts get-caller-identity`)
- [ ] S3 bucket exists and is accessible
- [ ] SageMaker role has correct permissions
- [ ] Bedrock access is enabled for Claude Sonnet 4
- [ ] Baseline model endpoint is deployed and accessible
- [ ] Use case has at least 5 test questions
- [ ] All prompts are non-empty and well-formatted
- [ ] Configuration values are within valid ranges

## Best Practices

### Configuration Management

1. **Version Control**: Keep configurations in git
   ```bash
   git add config/
   git commit -m "Add customer support use case"
   ```

2. **Environment Separation**: Use separate configs for dev/prod
   - Never test in production configuration
   - Use smaller datasets in development

3. **Secrets Management**: Never commit AWS credentials
   - Use environment variables or AWS credentials file
   - Add `*.credentials` to `.gitignore`

4. **Documentation**: Document custom configurations
   - Add comments explaining non-obvious settings
   - Keep this guide updated with changes

### Use Case Development

1. **Start Small**: Begin with a small dataset in development
   ```yaml
   # Development
   num_examples: 100
   max_iterations: 2
   ```

2. **Iterate on Prompts**: Test and refine prompts
   - Generate a small dataset
   - Review quality manually
   - Adjust prompts based on results

3. **Test Questions**: Start with 5-10 questions, expand later
   - Ensure questions are representative
   - Add edge cases gradually

4. **Gradual Scaling**: Increase dataset size as quality improves
   - 100 examples → 500 → 1000 → 2000+

### Cost Optimization

1. **Development**: Use minimal resources
   - Small instances (ml.g5.xlarge)
   - Small datasets (500 examples)
   - Enable auto cleanup
   - Short retention periods

2. **Production**: Balance cost and quality
   - Right-size instances based on needs
   - Monitor costs with AWS Cost Explorer
   - Delete unused endpoints
   - Use spot instances for training (if available)

3. **Monitoring**: Track costs per use case
   - Tag resources with use case name
   - Set up billing alerts
   - Review costs regularly

### Security Best Practices

1. **IAM Roles**: Use least privilege principle
   - Grant only necessary permissions
   - Use separate roles for dev/prod
   - Regularly audit permissions

2. **Encryption**: Enable encryption at rest
   - S3 bucket encryption
   - SageMaker volume encryption
   - Use KMS keys for sensitive data

3. **Access Control**: Restrict configuration access
   - Limit who can modify production configs
   - Require reviews for configuration changes
   - Audit configuration changes

4. **Secrets**: Never hardcode credentials
   - Use AWS Secrets Manager or Parameter Store
   - Rotate credentials regularly
   - Use IAM roles instead of access keys when possible

## Troubleshooting

### Common Issues

#### 1. "Access Denied" Errors

**Symptom**: Pipeline fails with AWS access denied errors

**Causes**:
- Incorrect IAM role permissions
- Wrong AWS credentials
- Bedrock access not enabled

**Solutions**:
```bash
# Check current AWS identity
aws sts get-caller-identity

# Verify SageMaker role exists
aws iam get-role --role-name SageMakerFinetuningRole

# Check Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

#### 2. "Endpoint Not Found" Errors

**Symptom**: Pipeline fails when trying to use baseline model

**Cause**: Baseline endpoint not deployed or wrong name

**Solution**:
```bash
# List existing endpoints
aws sagemaker list-endpoints

# Update configuration with correct endpoint name
```

#### 3. Training Job Failures

**Symptom**: SageMaker training job fails

**Common Causes**:
- Invalid training data format
- Insufficient instance resources
- Timeout exceeded

**Solutions**:
```bash
# Check training job logs
aws sagemaker describe-training-job --training-job-name JOB_NAME

# View CloudWatch logs
aws logs tail /aws/sagemaker/TrainingJobs --follow
```

#### 4. Low Win Rates

**Symptom**: Finetuned model consistently loses to baseline

**Causes**:
- Poor quality training data
- Insufficient training examples
- Suboptimal prompts

**Solutions**:
1. Review generated training data manually
2. Increase dataset size
3. Refine data generation prompt
4. Adjust training hyperparameters
5. Let self-improvement run more iterations

#### 5. Configuration Validation Failures

**Symptom**: Configuration fails validation

**Solution**: Run validation with verbose output:
```bash
python -m src.configuration_manager validate --verbose config/your_config.yaml
```

### Getting Help

1. **Check Logs**: Review pipeline logs for detailed errors
   ```bash
   tail -f logs/pipeline_prod.log
   ```

2. **AWS Console**: Check AWS console for resource status
   - SageMaker → Training jobs
   - SageMaker → Endpoints
   - CloudWatch → Logs

3. **Validation**: Run configuration validation
   ```bash
   python -m src.configuration_manager validate-all
   ```

4. **Documentation**: Review the design document
   - `.kiro/specs/automated-llm-finetuning-pipeline/design.md`

### Debug Mode

Enable debug mode for more detailed logging:

```yaml
logging:
  level: DEBUG
  verbose_logging: true

development:
  debug_endpoints: true
```

Or set environment variable:
```bash
export PIPELINE_DEBUG=1
python -m src.pipeline run my_use_case
```

## Additional Resources

- [AWS SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Design Document](../.kiro/specs/automated-llm-finetuning-pipeline/design.md)
- [Requirements Document](../.kiro/specs/automated-llm-finetuning-pipeline/requirements.md)

## Support

For issues or questions:
1. Check this guide and troubleshooting section
2. Review the design and requirements documents
3. Check AWS service status
4. Contact your team's ML engineering support
