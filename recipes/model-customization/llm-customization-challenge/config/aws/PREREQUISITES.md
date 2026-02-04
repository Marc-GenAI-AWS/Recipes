# AWS Prerequisites and Setup Guide

## Overview

This guide covers all prerequisites and setup steps required before running the automated LLM finetuning pipeline. Follow these steps in order to ensure a smooth setup experience.

## Table of Contents

1. [AWS Account Requirements](#aws-account-requirements)
2. [Required AWS Services](#required-aws-services)
3. [AWS CLI Setup](#aws-cli-setup)
4. [IAM Permissions for Setup](#iam-permissions-for-setup)
5. [S3 Bucket Setup](#s3-bucket-setup)
6. [Bedrock Model Access](#bedrock-model-access)
7. [SageMaker Quotas](#sagemaker-quotas)
8. [IAM Role Creation](#iam-role-creation)
9. [Validation](#validation)
10. [Troubleshooting](#troubleshooting)

---

## 1. AWS Account Requirements

### Minimum Requirements

- **AWS Account**: Active AWS account with billing enabled
- **Account Type**: Individual or organization account
- **Region Support**: Account must support the following services in your chosen region:
  - Amazon SageMaker
  - Amazon Bedrock
  - Amazon S3
  - Amazon CloudWatch

### Recommended Regions

The following regions have full support for all required services:

| Region | Region Code | Bedrock Support | SageMaker Support | Recommended |
|--------|-------------|-----------------|-------------------|-------------|
| US East (N. Virginia) | us-east-1 | ✅ | ✅ | ✅ Best for testing |
| US West (Oregon) | us-west-2 | ✅ | ✅ | ✅ Good alternative |
| Europe (Frankfurt) | eu-central-1 | ✅ | ✅ | ✅ For EU users |
| Asia Pacific (Tokyo) | ap-northeast-1 | ✅ | ✅ | For APAC users |

**Note**: Bedrock availability varies by region. Check [AWS Bedrock regions](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-regions.html) for current availability.

### Cost Considerations

Before starting, understand the costs involved:


| Service | Typical Cost per Pipeline Run | Notes |
|---------|-------------------------------|-------|
| SageMaker Training | $1.50 - $5.00 | ml.g5.2xlarge, 1-3 hours |
| SageMaker Endpoint | $1.00 - $2.00 | ml.g5.xlarge, 1-2 hours |
| Bedrock (Claude Sonnet 4) | $0.50 - $5.00 | Data generation + judging |
| S3 Storage | $0.01 - $0.10 | Training data + models |
| CloudWatch Logs | $0.01 - $0.05 | Logging |
| **Total per Run** | **$3.00 - $12.00** | Varies by dataset size |

**Budget Recommendation**: Set up AWS Budgets with alerts at $50/month for testing.

---

## 2. Required AWS Services

### Enable Required Services

The following AWS services must be enabled in your account:

#### Amazon SageMaker
- **Purpose**: Model training and deployment
- **Required Features**:
  - SageMaker Training Jobs
  - SageMaker Endpoints
  - SageMaker JumpStart (for Llama models)
- **How to Enable**: Enabled by default in all AWS accounts

#### Amazon Bedrock
- **Purpose**: Claude Sonnet 4 for data generation and judging
- **Required Models**:
  - Claude 3.5 Sonnet v2 (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
  - Claude Sonnet 4 (`anthropic.claude-sonnet-4-20250514-v1:0`)
- **How to Enable**:
  1. Go to AWS Console → Bedrock
  2. Navigate to "Model access" in the left sidebar
  3. Click "Manage model access"
  4. Select "Anthropic" and check "Claude 3.5 Sonnet" and "Claude Sonnet 4"
  5. Click "Request model access"
  6. Wait for approval (usually instant for Claude models)


#### Amazon S3
- **Purpose**: Store training data, model artifacts, and results
- **Required Features**:
  - Bucket creation
  - Object read/write
  - Lifecycle policies (optional, for cost optimization)
- **How to Enable**: Enabled by default in all AWS accounts

#### Amazon CloudWatch
- **Purpose**: Logging and monitoring
- **Required Features**:
  - CloudWatch Logs
  - CloudWatch Metrics (optional)
- **How to Enable**: Enabled by default in all AWS accounts

### Service Quotas Check

Check your service quotas to ensure you can run the pipeline:

```bash
# Check SageMaker quotas
aws service-quotas get-service-quota \
  --service-code sagemaker \
  --quota-code L-1E655831  # ml.g5.2xlarge for training

aws service-quotas get-service-quota \
  --service-code sagemaker \
  --quota-code L-9CCBF3F8  # ml.g5.xlarge for hosting

# Check Bedrock quotas
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-3E8EF5D4  # Requests per minute
```

**Minimum Required Quotas**:
- SageMaker Training: 1x ml.g5.2xlarge instance
- SageMaker Hosting: 1x ml.g5.xlarge instance
- Bedrock: 100 requests per minute

---

## 3. AWS CLI Setup

### Install AWS CLI


#### macOS/Linux
```bash
# Download and install
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify installation
aws --version
```

#### Windows
```powershell
# Download installer from: https://awscli.amazonaws.com/AWSCLIV2.msi
# Run installer and follow prompts

# Verify installation
aws --version
```

### Configure AWS CLI

```bash
# Configure with your credentials
aws configure

# You'll be prompted for:
# - AWS Access Key ID: [Your access key]
# - AWS Secret Access Key: [Your secret key]
# - Default region name: us-east-1 (or your preferred region)
# - Default output format: json
```

### Verify Configuration

```bash
# Test AWS CLI access
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }
```

---

## 4. IAM Permissions for Setup

### Required Permissions for Setup User

To create the IAM role and set up resources, your IAM user needs these permissions:


```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:AttachRolePolicy",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:TagRole",
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::*:role/SageMaker*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:PutBucketTagging"
      ],
      "Resource": "arn:aws:s3:::*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DeleteStack"
      ],
      "Resource": "*"
    }
  ]
}
```

### Check Your Current Permissions

```bash
# Check if you can create IAM roles
aws iam simulate-principal-policy \
  --policy-source-arn $(aws sts get-caller-identity --query Arn --output text) \
  --action-names iam:CreateRole iam:PutRolePolicy

# Expected output should show "allowed" for both actions
```


### If You Don't Have Permissions

If you don't have the required permissions:

1. **Option 1**: Ask your AWS administrator to grant you the permissions above
2. **Option 2**: Ask your administrator to create the IAM role for you using the templates in `config/aws/`
3. **Option 3**: Use AWS Organizations with delegated administration

---

## 5. S3 Bucket Setup

### Create S3 Bucket

The pipeline requires an S3 bucket to store training data and model artifacts.

#### Using AWS CLI

```bash
# Set your bucket name (must be globally unique)
BUCKET_NAME="my-llm-finetuning-$(date +%s)"

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region us-east-1

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled

# Add lifecycle policy to delete old artifacts (optional)
cat > lifecycle-policy.json << EOF
{
  "Rules": [
    {
      "Id": "DeleteOldTrainingData",
      "Status": "Enabled",
      "Prefix": "training_data/",
      "Expiration": {
        "Days": 30
      }
    },
    {
      "Id": "DeleteOldModels",
      "Status": "Enabled",
      "Prefix": "models/",
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket ${BUCKET_NAME} \
  --lifecycle-configuration file://lifecycle-policy.json
```


#### Using AWS Console

1. Go to AWS Console → S3
2. Click "Create bucket"
3. Enter bucket name (must be globally unique)
4. Select region (same as your pipeline region)
5. Keep default settings or enable:
   - Versioning (recommended)
   - Server-side encryption (recommended)
6. Click "Create bucket"

### Bucket Naming Best Practices

- Use lowercase letters, numbers, and hyphens only
- Include your organization name or project identifier
- Include a timestamp or random suffix for uniqueness
- Examples:
  - `acme-llm-finetuning-prod`
  - `my-sagemaker-pipeline-20240115`
  - `llm-training-data-dev`

### Verify Bucket Access

```bash
# Test write access
echo "test" > test.txt
aws s3 cp test.txt s3://${BUCKET_NAME}/test.txt

# Test read access
aws s3 cp s3://${BUCKET_NAME}/test.txt test-download.txt

# Clean up test file
aws s3 rm s3://${BUCKET_NAME}/test.txt
rm test.txt test-download.txt
```

---

## 6. Bedrock Model Access

### Enable Claude Models


#### Using AWS Console

1. Go to AWS Console → Bedrock
2. In the left sidebar, click "Model access"
3. Click "Manage model access" button
4. Find "Anthropic" in the list
5. Check the boxes for:
   - ✅ Claude 3.5 Sonnet
   - ✅ Claude Sonnet 4 (if available)
6. Click "Request model access"
7. Wait for approval (usually instant)

#### Using AWS CLI

```bash
# Check current model access
aws bedrock list-foundation-models \
  --by-provider anthropic \
  --query 'modelSummaries[*].[modelId,modelName]' \
  --output table

# Request access (if not already granted)
# Note: This typically requires console access for first-time setup
```

### Verify Bedrock Access

```bash
# Test Claude Sonnet 4 access
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-sonnet-4-20250514-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","messages":[{"role":"user","content":"Hello"}],"max_tokens":100}' \
  --cli-binary-format raw-in-base64-out \
  response.json

# Check response
cat response.json

# Expected: JSON response with Claude's greeting
```

### Bedrock Pricing

Understand Bedrock pricing before running the pipeline:

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Claude 3.5 Sonnet v2 | $3.00 | $15.00 |
| Claude Sonnet 4 | $3.00 | $15.00 |

**Typical Pipeline Usage**:
- Data generation: 50K-200K tokens (~$0.50-$2.00)
- Judging: 50K-300K tokens (~$0.50-$3.00)
- Self-improvement: 10K-50K tokens (~$0.10-$0.50)
- **Total per run**: $1.00-$5.00


---

## 7. SageMaker Quotas

### Check Current Quotas

```bash
# Check training instance quota (ml.g5.2xlarge)
aws service-quotas get-service-quota \
  --service-code sagemaker \
  --quota-code L-1E655831 \
  --region us-east-1

# Check hosting instance quota (ml.g5.xlarge)
aws service-quotas get-service-quota \
  --service-code sagemaker \
  --quota-code L-9CCBF3F8 \
  --region us-east-1
```

### Required Quotas

| Instance Type | Purpose | Minimum Quota | Recommended Quota |
|---------------|---------|---------------|-------------------|
| ml.g5.2xlarge | Training | 1 instance | 2 instances |
| ml.g5.xlarge | Inference | 1 instance | 2 instances |

### Request Quota Increase

If your quotas are insufficient:

#### Using AWS Console

1. Go to AWS Console → Service Quotas
2. Search for "SageMaker"
3. Find the quota you need to increase
4. Click "Request quota increase"
5. Enter desired value
6. Submit request
7. Wait for approval (usually 1-2 business days)

#### Using AWS CLI

```bash
# Request increase for training instances
aws service-quotas request-service-quota-increase \
  --service-code sagemaker \
  --quota-code L-1E655831 \
  --desired-value 2

# Request increase for hosting instances
aws service-quotas request-service-quota-increase \
  --service-code sagemaker \
  --quota-code L-9CCBF3F8 \
  --desired-value 2
```


### Alternative Instance Types

If you can't get ml.g5 instances, you can use alternatives:

| Alternative | Performance | Cost | Notes |
|-------------|-------------|------|-------|
| ml.g4dn.2xlarge | 70% of ml.g5 | 60% of ml.g5 | Good budget option |
| ml.p3.2xlarge | 80% of ml.g5 | 120% of ml.g5 | Older generation |
| ml.g5.4xlarge | 200% of ml.g5 | 200% of ml.g5 | Faster but expensive |

Update `config/pipeline_config.yaml` to use alternative instances:

```yaml
training:
  instance_type: ml.g4dn.2xlarge  # Instead of ml.g5.2xlarge

inference:
  instance_type: ml.g4dn.xlarge   # Instead of ml.g5.xlarge
```

---

## 8. IAM Role Creation

### Choose Your Setup Method

The pipeline provides three methods to create the required IAM role:

1. **CloudFormation** (Recommended) - AWS-native, easy rollback
2. **Terraform** - Infrastructure as code, version control
3. **Python Script** - Programmatic, scriptable

### Method 1: CloudFormation (Recommended)

```bash
# Navigate to project directory
cd /path/to/automated-llm-finetuning-pipeline

# Create the IAM role
aws cloudformation create-stack \
  --stack-name sagemaker-finetuning-role \
  --template-body file://config/aws/cloudformation/sagemaker-role.yaml \
  --parameters ParameterKey=S3BucketName,ParameterValue=${BUCKET_NAME} \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for stack creation (takes 1-2 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name sagemaker-finetuning-role \
  --region us-east-1

# Get the role ARN
ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name sagemaker-finetuning-role \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text \
  --region us-east-1)

echo "Role ARN: ${ROLE_ARN}"
```


### Method 2: Terraform

```bash
# Navigate to Terraform directory
cd config/aws/terraform/

# Initialize Terraform
terraform init

# Preview changes
terraform plan -var="s3_bucket_name=${BUCKET_NAME}"

# Apply configuration
terraform apply -var="s3_bucket_name=${BUCKET_NAME}" -auto-approve

# Get the role ARN
ROLE_ARN=$(terraform output -raw role_arn)
echo "Role ARN: ${ROLE_ARN}"
```

### Method 3: Python Script

```bash
# Install boto3 if not already installed
pip install boto3

# Run the setup script
python config/aws/scripts/create_iam_role.py \
  --bucket-name ${BUCKET_NAME} \
  --region us-east-1

# The script will output the role ARN
```

### Advanced Options

#### Enable VPC Access (Optional)

If you need to run SageMaker in a VPC:

```bash
# CloudFormation
aws cloudformation create-stack \
  --stack-name sagemaker-finetuning-role \
  --template-body file://config/aws/cloudformation/sagemaker-role.yaml \
  --parameters \
    ParameterKey=S3BucketName,ParameterValue=${BUCKET_NAME} \
    ParameterKey=EnableVPCAccess,ParameterValue=true \
  --capabilities CAPABILITY_NAMED_IAM

# Terraform
terraform apply \
  -var="s3_bucket_name=${BUCKET_NAME}" \
  -var="enable_vpc_access=true"

# Python
python config/aws/scripts/create_iam_role.py \
  --bucket-name ${BUCKET_NAME} \
  --enable-vpc
```


#### Enable KMS Encryption (Optional)

If you use customer-managed KMS keys for S3 encryption:

```bash
# Get your KMS key ARN
KMS_KEY_ARN=$(aws kms describe-key --key-id alias/my-key --query 'KeyMetadata.Arn' --output text)

# CloudFormation
aws cloudformation create-stack \
  --stack-name sagemaker-finetuning-role \
  --template-body file://config/aws/cloudformation/sagemaker-role.yaml \
  --parameters \
    ParameterKey=S3BucketName,ParameterValue=${BUCKET_NAME} \
    ParameterKey=EnableKMSEncryption,ParameterValue=true \
    ParameterKey=KMSKeyArn,ParameterValue=${KMS_KEY_ARN} \
  --capabilities CAPABILITY_NAMED_IAM

# Terraform
terraform apply \
  -var="s3_bucket_name=${BUCKET_NAME}" \
  -var="enable_kms_encryption=true" \
  -var="kms_key_arn=${KMS_KEY_ARN}"

# Python
python config/aws/scripts/create_iam_role.py \
  --bucket-name ${BUCKET_NAME} \
  --enable-kms \
  --kms-key-arn ${KMS_KEY_ARN}
```

---

## 9. Validation

### Validate IAM Role Permissions

After creating the IAM role, validate that all permissions are correctly configured:

```bash
# Run validation script
python config/aws/scripts/validate_permissions.py \
  --role-arn ${ROLE_ARN}

# Expected output:
# ✓ Role exists and is assumable by SageMaker
# ✓ S3 read/write permissions
# ✓ SageMaker training and deployment permissions
# ✓ Bedrock model invocation permissions
# ✓ CloudWatch logging permissions
# All validations passed!
```


### Update Pipeline Configuration

Update your pipeline configuration with the created resources:

```bash
# Create or update config/pipeline_config.yaml
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

echo "Configuration updated successfully!"
```

### Test End-to-End Setup

Run a minimal test to verify everything is working:

```bash
# Test S3 access
python -c "
import boto3
s3 = boto3.client('s3', region_name='us-east-1')
s3.put_object(Bucket='${BUCKET_NAME}', Key='test.txt', Body=b'test')
print('✓ S3 access working')
"

# Test Bedrock access
python -c "
import boto3
import json
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
response = bedrock.invoke_model(
    modelId='anthropic.claude-sonnet-4-20250514-v1:0',
    body=json.dumps({
        'anthropic_version': 'bedrock-2023-05-31',
        'messages': [{'role': 'user', 'content': 'Hello'}],
        'max_tokens': 10
    })
)
print('✓ Bedrock access working')
"

# Test IAM role
python -c "
import boto3
iam = boto3.client('iam')
role = iam.get_role(RoleName='SageMakerFinetuningRole')
print('✓ IAM role exists')
"

echo "All tests passed! Setup is complete."
```


---

## 10. Troubleshooting

### Common Issues and Solutions

#### Issue: "Access Denied" when creating IAM role

**Symptoms**:
```
An error occurred (AccessDenied) when calling the CreateRole operation
```

**Solutions**:
1. Check your IAM user has `iam:CreateRole` permission
2. Verify you're not blocked by a permission boundary
3. Try using a different role name (may conflict with existing role)
4. Contact your AWS administrator for assistance

#### Issue: "Bucket already exists" error

**Symptoms**:
```
An error occurred (BucketAlreadyExists) when calling the CreateBucket operation
```

**Solutions**:
1. S3 bucket names must be globally unique
2. Add a timestamp or random suffix to your bucket name
3. Use a different bucket name

```bash
# Generate unique bucket name
BUCKET_NAME="my-llm-finetuning-$(date +%s)-$(openssl rand -hex 4)"
```

#### Issue: "Model access not granted" for Bedrock

**Symptoms**:
```
An error occurred (AccessDeniedException) when calling the InvokeModel operation
```

**Solutions**:
1. Go to AWS Console → Bedrock → Model access
2. Verify Claude models are enabled
3. Wait a few minutes after requesting access
4. Check you're in a region that supports Bedrock
5. Verify the model ID is correct

#### Issue: "Service quota exceeded" for SageMaker

**Symptoms**:
```
ResourceLimitExceeded: The account-level service limit 'ml.g5.2xlarge for training job usage' is 0 Instances
```

**Solutions**:
1. Request quota increase (see section 7)
2. Use alternative instance type (ml.g4dn.2xlarge)
3. Wait for existing training jobs to complete
4. Try a different region with available capacity


#### Issue: "Region not supported" error

**Symptoms**:
```
An error occurred (InvalidParameterValueException): Bedrock is not available in this region
```

**Solutions**:
1. Check Bedrock availability: https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-regions.html
2. Use a supported region (us-east-1, us-west-2, eu-central-1)
3. Update all configurations to use the same region

#### Issue: CloudFormation stack creation fails

**Symptoms**:
```
Stack creation failed: CREATE_FAILED
```

**Solutions**:
1. Check CloudFormation events for specific error
```bash
aws cloudformation describe-stack-events \
  --stack-name sagemaker-finetuning-role \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```
2. Verify you have CAPABILITY_NAMED_IAM capability
3. Check parameter values are correct
4. Delete failed stack and retry:
```bash
aws cloudformation delete-stack --stack-name sagemaker-finetuning-role
```

#### Issue: Validation script fails

**Symptoms**:
```
✗ S3 read/write permissions failed
```

**Solutions**:
1. Check the specific permission that failed
2. Verify S3 bucket name in IAM policy matches your bucket
3. Ensure IAM role has been created successfully
4. Wait a few minutes for IAM changes to propagate
5. Re-run validation script

### Getting Help

If you're still experiencing issues:

1. **Check AWS Service Health**: https://status.aws.amazon.com/
2. **Review AWS Documentation**:
   - [SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/)
   - [Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
   - [IAM Documentation](https://docs.aws.amazon.com/IAM/)
3. **Check CloudTrail Logs**:
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AccessDenied \
  --max-results 10
```
4. **Contact AWS Support**: If you have a support plan
5. **Open GitHub Issue**: For pipeline-specific issues


---

## Setup Checklist

Use this checklist to track your setup progress:

### Pre-Setup
- [ ] AWS account is active with billing enabled
- [ ] Chosen region supports all required services
- [ ] Budget alerts configured (recommended: $50/month)
- [ ] AWS CLI installed and configured
- [ ] IAM user has required setup permissions

### Service Enablement
- [ ] Amazon SageMaker is accessible
- [ ] Amazon Bedrock is enabled in your region
- [ ] Claude 3.5 Sonnet model access granted
- [ ] Claude Sonnet 4 model access granted (if available)
- [ ] Amazon S3 is accessible
- [ ] Amazon CloudWatch is accessible

### Resource Creation
- [ ] S3 bucket created with unique name
- [ ] S3 bucket versioning enabled (optional)
- [ ] S3 lifecycle policies configured (optional)
- [ ] S3 bucket access verified

### Quota Verification
- [ ] SageMaker training quota checked (ml.g5.2xlarge)
- [ ] SageMaker hosting quota checked (ml.g5.xlarge)
- [ ] Bedrock rate limits checked
- [ ] Quota increase requested if needed

### IAM Role Setup
- [ ] IAM role creation method chosen
- [ ] IAM role created successfully
- [ ] Role ARN obtained and saved
- [ ] VPC access enabled (if required)
- [ ] KMS encryption enabled (if required)

### Validation
- [ ] IAM role permissions validated
- [ ] S3 access tested
- [ ] Bedrock access tested
- [ ] Pipeline configuration updated
- [ ] End-to-end test completed

### Documentation
- [ ] Role ARN documented
- [ ] S3 bucket name documented
- [ ] Region documented
- [ ] Any custom configurations documented

---

## Next Steps

After completing all prerequisites:

1. **Install Pipeline Dependencies**:
```bash
cd /path/to/automated-llm-finetuning-pipeline
pip install -r requirements.txt
```

2. **Create Your First Use Case**:
```bash
# Copy example use case
cp config/use_cases/customer_support.example.yaml \
   config/use_cases/my_use_case.yaml

# Edit with your requirements
nano config/use_cases/my_use_case.yaml
```

3. **Run the Pipeline**:
```bash
# Using Python
python -m src.pipeline --use-case my_use_case

# Or using Streamlit UI
streamlit run streamlit_app.py
```

4. **Monitor Costs**:
```bash
# Check current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

---

## Additional Resources

### Documentation
- [Main README](../../README.md) - Project overview
- [Configuration Guide](../CONFIGURATION_GUIDE.md) - Detailed configuration options
- [Quick Start Guide](../QUICK_START.md) - Get started quickly
- [AWS Setup README](README.md) - IAM role details
- [Permissions Explained](PERMISSIONS_EXPLAINED.md) - Detailed permission guide
- [Quick Reference](QUICK_REFERENCE.md) - Common commands

### AWS Resources
- [AWS Free Tier](https://aws.amazon.com/free/) - Free tier eligibility
- [AWS Pricing Calculator](https://calculator.aws/) - Estimate costs
- [AWS Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/) - Analyze spending
- [AWS Budgets](https://aws.amazon.com/aws-cost-management/aws-budgets/) - Set cost alerts

### Support
- **GitHub Issues**: Report bugs or request features
- **AWS Support**: Technical support (requires support plan)
- **Community**: Join discussions and share experiences

---

## Summary

You've completed the AWS prerequisites and setup! You should now have:

✅ AWS account with required services enabled
✅ AWS CLI configured
✅ S3 bucket for data storage
✅ Bedrock access for Claude models
✅ SageMaker quotas verified
✅ IAM role with proper permissions
✅ Pipeline configuration updated
✅ Setup validated and tested

**Estimated Setup Time**: 30-60 minutes
**Estimated Cost**: $0 (setup is free, costs occur during pipeline runs)

You're now ready to start using the automated LLM finetuning pipeline!

