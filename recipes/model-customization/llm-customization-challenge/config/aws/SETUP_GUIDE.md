# AWS Setup Guide - Step by Step

## Quick Setup (15 minutes)

This guide provides a streamlined setup process for getting started quickly. For detailed information, see [PREREQUISITES.md](PREREQUISITES.md).

---

## Step 1: Verify AWS Account (2 minutes)

### Check AWS CLI

```bash
# Verify AWS CLI is installed
aws --version

# If not installed, install it:
# macOS/Linux:
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows: Download from https://awscli.amazonaws.com/AWSCLIV2.msi
```

### Configure AWS CLI

```bash
# Configure credentials
aws configure

# Enter your:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Default output format (json)

# Verify configuration
aws sts get-caller-identity
```

**Expected Output**:
```json
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

---

## Step 2: Enable Bedrock Models (3 minutes)

### Using AWS Console

1. Open AWS Console: https://console.aws.amazon.com/bedrock/
2. Click **"Model access"** in left sidebar
3. Click **"Manage model access"** button
4. Find **"Anthropic"** section
5. Check boxes for:
   - ✅ Claude 3.5 Sonnet
   - ✅ Claude Sonnet 4
6. Click **"Request model access"**
7. Wait for approval (usually instant)

### Verify Access

```bash
aws bedrock list-foundation-models \
  --by-provider anthropic \
  --region us-east-1 \
  --query 'modelSummaries[*].[modelId,modelName]' \
  --output table
```

**Expected**: Table showing Claude models

---

## Step 3: Create S3 Bucket (2 minutes)

```bash
# Generate unique bucket name
BUCKET_NAME="llm-finetuning-$(date +%s)"
echo "Bucket name: ${BUCKET_NAME}"

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region us-east-1

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled

# Verify bucket
aws s3 ls s3://${BUCKET_NAME}
```

**Save your bucket name** - you'll need it in the next steps!

---

## Step 4: Create IAM Role (5 minutes)

### Option A: CloudFormation (Recommended)

```bash
# Navigate to project directory
cd /path/to/automated-llm-finetuning-pipeline

# Create IAM role
aws cloudformation create-stack \
  --stack-name sagemaker-finetuning-role \
  --template-body file://config/aws/cloudformation/sagemaker-role.yaml \
  --parameters ParameterKey=S3BucketName,ParameterValue=${BUCKET_NAME} \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for completion (1-2 minutes)
echo "Waiting for stack creation..."
aws cloudformation wait stack-create-complete \
  --stack-name sagemaker-finetuning-role \
  --region us-east-1

# Get role ARN
ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name sagemaker-finetuning-role \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text \
  --region us-east-1)

echo "✓ IAM Role created successfully!"
echo "Role ARN: ${ROLE_ARN}"
```

### Option B: Python Script

```bash
# Install boto3
pip install boto3

# Run setup script
python config/aws/scripts/create_iam_role.py \
  --bucket-name ${BUCKET_NAME} \
  --region us-east-1

# Script will output the role ARN
```

### Option C: Terraform

```bash
cd config/aws/terraform/
terraform init
terraform apply -var="s3_bucket_name=${BUCKET_NAME}" -auto-approve
ROLE_ARN=$(terraform output -raw role_arn)
echo "Role ARN: ${ROLE_ARN}"
```

---

## Step 5: Validate Setup (2 minutes)

```bash
# Run validation script
python config/aws/scripts/validate_permissions.py --role-arn ${ROLE_ARN}
```

**Expected Output**:
```
Validating IAM role permissions...
✓ Role exists and is assumable by SageMaker
✓ S3 read/write permissions
✓ SageMaker training and deployment permissions
✓ Bedrock model invocation permissions
✓ CloudWatch logging permissions

All validations passed!
```

---

## Step 6: Configure Pipeline (1 minute)

```bash
# Create pipeline configuration
cat > config/pipeline_config.yaml << EOF
aws:
  region: us-east-1
  bedrock_model_id: anthropic.claude-sonnet-4-20250514-v1:0
  sagemaker_role_arn: ${ROLE_ARN}
  s3_bucket: ${BUCKET_NAME}

training:
  base_model: meta-llama/Llama-3.2-3B
  instance_type: ml.g5.2xlarge
  max_training_time_seconds: 86400

inference:
  instance_type: ml.g5.xlarge
  baseline_model_endpoint: llama-70b-baseline

pipeline:
  performance_threshold: 0.60
  max_iterations: 5
  cleanup_resources: true
  artifact_retention_days: 7

retry:
  max_attempts: 3
  initial_backoff_seconds: 2
  max_backoff_seconds: 60
EOF

echo "✓ Pipeline configuration created!"
```

---

## Step 7: Test Setup (Optional, 1 minute)

```bash
# Test S3 access
echo "test" > test.txt
aws s3 cp test.txt s3://${BUCKET_NAME}/test.txt
aws s3 rm s3://${BUCKET_NAME}/test.txt
rm test.txt
echo "✓ S3 access working"

# Test Bedrock access
python -c "
import boto3, json
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
response = bedrock.invoke_model(
    modelId='anthropic.claude-sonnet-4-20250514-v1:0',
    body=json.dumps({
        'anthropic_version': 'bedrock-2023-05-31',
        'messages': [{'role': 'user', 'content': 'Hi'}],
        'max_tokens': 10
    })
)
print('✓ Bedrock access working')
"
```

---

## Setup Complete! 🎉

You're ready to use the pipeline. Here's what you have:

✅ AWS CLI configured
✅ Bedrock models enabled (Claude)
✅ S3 bucket created: `${BUCKET_NAME}`
✅ IAM role created: `${ROLE_ARN}`
✅ Pipeline configured
✅ Setup validated

### Your Configuration Summary

```bash
echo "=== Your AWS Configuration ==="
echo "Region: us-east-1"
echo "S3 Bucket: ${BUCKET_NAME}"
echo "IAM Role ARN: ${ROLE_ARN}"
echo "Bedrock Model: anthropic.claude-sonnet-4-20250514-v1:0"
echo "=============================="
```

**Save these values** for future reference!

---

## Next Steps

### 1. Install Pipeline Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Your First Use Case

```bash
# Copy example
cp config/use_cases/customer_support.example.yaml \
   config/use_cases/my_first_use_case.yaml

# Edit the file
nano config/use_cases/my_first_use_case.yaml
```

### 3. Run the Pipeline

**Option A: Command Line**
```bash
python -m src.pipeline --use-case my_first_use_case
```

**Option B: Streamlit UI**
```bash
streamlit run streamlit_app.py
```

---

## Troubleshooting

### "Access Denied" Errors

```bash
# Check your IAM permissions
aws iam get-user

# Verify role exists
aws iam get-role --role-name SageMakerFinetuningRole
```

### "Bucket Already Exists" Error

```bash
# Generate new unique bucket name
BUCKET_NAME="llm-finetuning-$(date +%s)-$(openssl rand -hex 4)"
echo "New bucket name: ${BUCKET_NAME}"

# Retry bucket creation
aws s3 mb s3://${BUCKET_NAME} --region us-east-1
```

### "Model Access Not Granted"

1. Go to AWS Console → Bedrock → Model access
2. Verify Claude models show "Access granted"
3. Wait 2-3 minutes and retry
4. Check you're in the correct region

### CloudFormation Stack Failed

```bash
# Check what failed
aws cloudformation describe-stack-events \
  --stack-name sagemaker-finetuning-role \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'

# Delete and retry
aws cloudformation delete-stack --stack-name sagemaker-finetuning-role
# Wait a minute, then retry Step 4
```

---

## Cost Monitoring

### Set Up Budget Alert

```bash
# Create budget for $50/month
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://<(cat << EOF
{
  "BudgetName": "LLM-Finetuning-Budget",
  "BudgetLimit": {
    "Amount": "50",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
EOF
)
```

### Check Current Costs

```bash
# View this month's costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

---

## Cleanup (When Done)

To remove all AWS resources:

```bash
# Delete IAM role
aws cloudformation delete-stack --stack-name sagemaker-finetuning-role

# Delete S3 bucket (remove all objects first)
aws s3 rm s3://${BUCKET_NAME} --recursive
aws s3 rb s3://${BUCKET_NAME}

# Verify cleanup
aws cloudformation list-stacks --stack-status-filter DELETE_COMPLETE
aws s3 ls | grep ${BUCKET_NAME}
```

---

## Additional Resources

- **Detailed Prerequisites**: [PREREQUISITES.md](PREREQUISITES.md)
- **Permission Details**: [PERMISSIONS_EXPLAINED.md](PERMISSIONS_EXPLAINED.md)
- **Quick Commands**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Main Documentation**: [README.md](README.md)

---

## Support

Need help? Check:

1. **Troubleshooting section** above
2. **[PREREQUISITES.md](PREREQUISITES.md)** for detailed guidance
3. **AWS Service Health**: https://status.aws.amazon.com/
4. **GitHub Issues**: Report problems or ask questions

---

**Estimated Setup Time**: 15 minutes
**Estimated Cost**: $0 (setup is free)

Happy finetuning! 🚀
