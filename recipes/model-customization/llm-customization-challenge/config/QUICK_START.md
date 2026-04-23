# Quick Start Guide

Get started with the automated LLM finetuning pipeline in 5 minutes.

## Prerequisites

- AWS account with access to SageMaker and Bedrock
- AWS CLI configured with credentials
- Python 3.10+ installed

## Step 1: Configure AWS (5 minutes)

### 1.1 Create S3 Bucket

```bash
aws s3 mb s3://my-finetuning-bucket --region us-east-1
```

### 1.2 Create SageMaker Role

```bash
# Create trust policy file
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "sagemaker.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name SageMakerFinetuningRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name SageMakerFinetuningRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

aws iam attach-role-policy \
  --role-name SageMakerFinetuningRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Get role ARN (save this for next step)
aws iam get-role --role-name SageMakerFinetuningRole --query 'Role.Arn' --output text
```

### 1.3 Enable Bedrock Access

1. Go to AWS Console → Bedrock → Model access
2. Request access to "Claude Sonnet 4"
3. Wait for approval (usually instant)

## Step 2: Configure Pipeline (2 minutes)

### 2.1 Copy Development Configuration

```bash
cp config/pipeline_config.dev.yaml config/pipeline_config.yaml
```

### 2.2 Update Required Settings

Edit `config/pipeline_config.yaml`:

```yaml
aws:
  region: us-east-1  # Your AWS region
  sagemaker_role_arn: arn:aws:iam::YOUR_ACCOUNT:role/SageMakerFinetuningRole  # From step 1.2
  s3_bucket: my-finetuning-bucket  # From step 1.1
```

## Step 3: Create Your First Use Case (3 minutes)

### 3.1 Copy Template

```bash
cp config/use_cases/template.yaml config/use_cases/my_first_use_case.yaml
```

### 3.2 Customize Use Case

Edit `config/use_cases/my_first_use_case.yaml`:

```yaml
name: my_first_use_case

description: |
  A simple use case to test the pipeline.
  The model should provide helpful, friendly responses.

test_questions:
  - "What is machine learning?"
  - "How do I get started with Python?"
  - "Explain neural networks simply."
  - "What's the difference between AI and ML?"
  - "How does deep learning work?"

judge_criteria: |
  Evaluate responses based on:
  1. Clarity - Is it easy to understand?
  2. Accuracy - Is the information correct?
  3. Helpfulness - Does it answer the question?

data_generation_prompt: |
  Generate educational Q&A examples about technology and programming.
  Each example should have a question and a clear, helpful answer.
  
  Format:
  {
    "instruction": "Answer this question clearly and helpfully.",
    "context": "[A question about technology or programming]",
    "response": "[A clear, accurate, helpful answer]"
  }

judge_prompt: |
  Compare Response A and Response B for the given question.
  Choose the response that is clearer, more accurate, and more helpful.
  
  Output:
  {
    "winner": "A" or "B" or "tie",
    "reasoning": "Explanation of your choice",
    "confidence": 0.0 to 1.0
  }
```

### 3.3 Validate Configuration

```bash
python -m src.configuration_manager validate config/use_cases/my_first_use_case.yaml
```

## Step 4: Run the Pipeline (Optional - requires baseline model)

**Note**: This step requires a deployed baseline 70B model endpoint, which is expensive (~$7/hour). For your first test, you may want to skip this and just validate your configuration.

### 4.1 Deploy Baseline Model (if needed)

```python
from sagemaker.jumpstart.model import JumpStartModel

baseline_model = JumpStartModel(
    model_id="meta-textgeneration-llama-3-1-70b",
    role="arn:aws:iam::YOUR_ACCOUNT:role/SageMakerFinetuningRole"
)

baseline_predictor = baseline_model.deploy(
    instance_type="ml.g5.12xlarge",
    initial_instance_count=1,
    endpoint_name="llama-70b-baseline"
)
```

Update your configuration with the endpoint name:
```yaml
inference:
  baseline_model_endpoint: llama-70b-baseline
```

### 4.2 Run Pipeline

```bash
python -m src.pipeline run my_first_use_case
```

Or use the Streamlit UI:
```bash
streamlit run streamlit_app.py
```

## Common Scenarios

### Scenario 1: Testing Without AWS Costs

For testing the configuration without AWS costs:

```yaml
# In pipeline_config.yaml
development:
  mock_aws_calls: true  # Enable mock mode
```

Then run:
```bash
python -m src.pipeline run my_first_use_case --mock
```

### Scenario 2: Small Test Run

For a quick, cheap test run:

```yaml
# In use case custom_config
custom_config:
  num_examples: 100  # Very small dataset
  training_epochs: 1  # Minimal training
  max_iterations: 1  # No self-improvement
```

Estimated cost: ~$5-10

### Scenario 3: Production Quality Run

For production-quality results:

```yaml
# Use production configuration
cp config/pipeline_config.prod.yaml config/pipeline_config.yaml

# In use case custom_config
custom_config:
  num_examples: 2000  # Large dataset
  training_epochs: 5  # Full training
  max_iterations: 5  # Full self-improvement
```

Estimated cost: ~$50-100

## Next Steps

1. **Review Results**: Check `progress/` directory for iteration results
2. **Refine Prompts**: Adjust data generation and judge prompts based on results
3. **Scale Up**: Increase dataset size and iterations for better quality
4. **Monitor Costs**: Use AWS Cost Explorer to track spending
5. **Read Full Guide**: See `CONFIGURATION_GUIDE.md` for detailed documentation

## Troubleshooting

### "Access Denied" Error

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check SageMaker role
aws iam get-role --role-name SageMakerFinetuningRole
```

### "Bedrock Access Denied"

1. Go to AWS Console → Bedrock → Model access
2. Ensure Claude Sonnet 4 is enabled
3. Wait a few minutes for access to propagate

### "S3 Bucket Not Found"

```bash
# Verify bucket exists
aws s3 ls s3://my-finetuning-bucket

# Create if missing
aws s3 mb s3://my-finetuning-bucket --region us-east-1
```

### Configuration Validation Fails

```bash
# Run validation with verbose output
python -m src.configuration_manager validate --verbose config/use_cases/my_first_use_case.yaml
```

## Cost Estimates

### Development Run (Small Dataset)
- Data generation (100 examples): ~$0.50
- Training (1 hour, ml.g5.xlarge): ~$1.50
- Inference (10 questions): ~$0.10
- **Total: ~$2-3**

### Production Run (Large Dataset)
- Data generation (2000 examples): ~$10
- Training (4 hours, ml.g5.2xlarge): ~$10
- Inference (20 questions): ~$0.20
- Self-improvement (2 iterations): ~$20
- **Total: ~$40-50**

### Baseline Model (if deployed)
- ml.g5.12xlarge: ~$7/hour
- **Remember to delete when not in use!**

## Getting Help

- **Configuration Guide**: `config/CONFIGURATION_GUIDE.md`
- **Design Document**: `.kiro/specs/automated-llm-finetuning-pipeline/design.md`
- **AWS Documentation**: https://docs.aws.amazon.com/sagemaker/

## Example Commands

```bash
# Validate all configurations
python -m src.configuration_manager validate-all

# List available use cases
python -m src.configuration_manager list-use-cases

# Run pipeline with specific config
python -m src.pipeline run my_use_case --config config/pipeline_config.dev.yaml

# Resume interrupted pipeline
python -m src.pipeline resume my_use_case --state-id STATE_ID

# View results
python -m src.progress_tracker report my_use_case

# Clean up resources
python -m src.cleanup delete-endpoints --use-case my_use_case
```

## Tips for Success

1. **Start Small**: Begin with 100 examples and 1 iteration
2. **Validate Early**: Always validate configurations before running
3. **Monitor Costs**: Set up AWS billing alerts
4. **Iterate Prompts**: Refine prompts based on generated data quality
5. **Review Results**: Manually review training data and judgments
6. **Clean Up**: Delete endpoints when not in use to save costs
7. **Use Version Control**: Keep configurations in git
8. **Document Changes**: Add comments explaining custom settings

## Ready to Go!

You're now ready to start finetuning models. Begin with a small test run to familiarize yourself with the pipeline, then scale up for production use.

Happy finetuning! 🚀
