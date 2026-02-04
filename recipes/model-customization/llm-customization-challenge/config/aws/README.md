# AWS IAM Role Setup for SageMaker Finetuning Pipeline

This directory contains IAM role templates and scripts to set up the required AWS permissions for the automated LLM finetuning pipeline.

## Overview

The pipeline requires an IAM role that SageMaker can assume to:
- Access training data in S3
- Store model artifacts in S3
- Write logs to CloudWatch
- Access Bedrock for Claude Sonnet 4
- Create and manage SageMaker resources

## Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - **START HERE!** Step-by-step setup (15 minutes)
- **[PREREQUISITES.md](PREREQUISITES.md)** - Detailed prerequisites and requirements
- **[PERMISSIONS_EXPLAINED.md](PERMISSIONS_EXPLAINED.md)** - Detailed permission explanations
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick command reference
- **[README.md](README.md)** - This file (overview and detailed options)

## Quick Start

### Option 1: CloudFormation (Recommended)

```bash
# Deploy the IAM role using CloudFormation
aws cloudformation create-stack \
  --stack-name sagemaker-finetuning-role \
  --template-body file://cloudformation/sagemaker-role.yaml \
  --parameters ParameterKey=S3BucketName,ParameterValue=your-bucket-name \
  --capabilities CAPABILITY_NAMED_IAM

# Wait for stack creation
aws cloudformation wait stack-create-complete \
  --stack-name sagemaker-finetuning-role

# Get the role ARN
aws cloudformation describe-stacks \
  --stack-name sagemaker-finetuning-role \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text
```

### Option 2: Terraform

```bash
cd terraform/
terraform init
terraform plan -var="s3_bucket_name=your-bucket-name"
terraform apply -var="s3_bucket_name=your-bucket-name"

# Get the role ARN
terraform output role_arn
```

### Option 3: Python Script

```bash
# Install boto3 if not already installed
pip install boto3

# Run the setup script
python scripts/create_iam_role.py --bucket-name your-bucket-name

# The script will output the role ARN
```

## Directory Structure

```
config/aws/
├── README.md                           # This file
├── policies/
│   ├── sagemaker-execution-policy.json # Main execution policy
│   ├── s3-access-policy.json          # S3 bucket access
│   ├── bedrock-access-policy.json     # Bedrock API access
│   ├── cloudwatch-logs-policy.json    # CloudWatch logging
│   └── trust-policy.json              # Trust relationship
├── cloudformation/
│   └── sagemaker-role.yaml            # CloudFormation template
├── terraform/
│   ├── main.tf                        # Terraform main config
│   ├── variables.tf                   # Terraform variables
│   ├── outputs.tf                     # Terraform outputs
│   └── README.md                      # Terraform-specific docs
└── scripts/
    ├── create_iam_role.py             # Python setup script
    ├── validate_permissions.py        # Permission validation
    └── cleanup_role.py                # Role cleanup script
```

## Required Permissions

### S3 Permissions
- `s3:GetObject` - Read training data and model artifacts
- `s3:PutObject` - Write model artifacts and results
- `s3:ListBucket` - List bucket contents
- `s3:DeleteObject` - Clean up temporary files

### SageMaker Permissions
- `sagemaker:CreateTrainingJob` - Start training jobs
- `sagemaker:DescribeTrainingJob` - Monitor training progress
- `sagemaker:CreateModel` - Create model resources
- `sagemaker:CreateEndpointConfig` - Configure endpoints
- `sagemaker:CreateEndpoint` - Deploy models
- `sagemaker:DescribeEndpoint` - Monitor endpoints
- `sagemaker:DeleteEndpoint` - Clean up endpoints
- `sagemaker:InvokeEndpoint` - Generate predictions

### Bedrock Permissions
- `bedrock:InvokeModel` - Call Claude Sonnet 4 for data generation and judging

### CloudWatch Permissions
- `logs:CreateLogGroup` - Create log groups
- `logs:CreateLogStream` - Create log streams
- `logs:PutLogEvents` - Write log events

## Security Best Practices

### Principle of Least Privilege
The IAM policies follow the principle of least privilege:
- S3 access is restricted to specific bucket(s)
- SageMaker permissions are limited to necessary operations
- Bedrock access is restricted to specific model IDs
- CloudWatch access is scoped to pipeline log groups

### Resource Restrictions
- S3 policies use bucket-specific ARNs
- CloudWatch policies use log group prefixes
- Bedrock policies specify exact model IDs

### Trust Policy
The trust policy only allows:
- SageMaker service principal (`sagemaker.amazonaws.com`)
- Optional: Specific AWS account IDs for cross-account access

## Customization

### Restricting to Specific Buckets

Edit the S3 policy to specify your bucket:

```json
{
  "Resource": [
    "arn:aws:s3:::your-specific-bucket",
    "arn:aws:s3:::your-specific-bucket/*"
  ]
}
```

### Adding VPC Configuration

If using VPC for SageMaker:

```json
{
  "Effect": "Allow",
  "Action": [
    "ec2:CreateNetworkInterface",
    "ec2:DescribeNetworkInterfaces",
    "ec2:DeleteNetworkInterface",
    "ec2:DescribeVpcs",
    "ec2:DescribeSubnets",
    "ec2:DescribeSecurityGroups"
  ],
  "Resource": "*"
}
```

### Adding KMS Encryption

If using KMS for S3 encryption:

```json
{
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt",
    "kms:Encrypt",
    "kms:GenerateDataKey"
  ],
  "Resource": "arn:aws:kms:region:account-id:key/key-id"
}
```

## Validation

After creating the role, validate permissions:

```bash
python scripts/validate_permissions.py --role-arn arn:aws:iam::123456789012:role/SageMakerFinetuningRole
```

This will check:
- ✓ Role exists and is assumable by SageMaker
- ✓ S3 read/write permissions
- ✓ SageMaker training and deployment permissions
- ✓ Bedrock model invocation permissions
- ✓ CloudWatch logging permissions

## Troubleshooting

### "Access Denied" Errors

1. **S3 Access Denied**: Verify bucket name in policy matches your bucket
2. **SageMaker Access Denied**: Ensure role has `sagemaker:CreateTrainingJob` permission
3. **Bedrock Access Denied**: Check model ID in policy matches the one you're using
4. **CloudWatch Access Denied**: Verify log group prefix matches your configuration

### Role Assumption Issues

If SageMaker cannot assume the role:
1. Check trust policy includes `sagemaker.amazonaws.com`
2. Verify role ARN is correct in pipeline configuration
3. Ensure role is in the same account as SageMaker resources

### Permission Boundary Issues

If your organization uses permission boundaries:
1. Ensure the boundary allows SageMaker operations
2. Contact your AWS administrator for boundary policies
3. The role must fit within the boundary constraints

## Cost Considerations

The IAM role itself has no cost, but the resources it accesses do:
- **SageMaker Training**: ~$1-5 per training job (ml.g5.2xlarge)
- **SageMaker Endpoints**: ~$1-2 per hour (ml.g5.xlarge)
- **Bedrock API**: ~$0.003 per 1K input tokens, ~$0.015 per 1K output tokens
- **S3 Storage**: ~$0.023 per GB per month
- **CloudWatch Logs**: ~$0.50 per GB ingested

## Cleanup

To remove the IAM role:

### CloudFormation
```bash
aws cloudformation delete-stack --stack-name sagemaker-finetuning-role
```

### Terraform
```bash
cd terraform/
terraform destroy -var="s3_bucket_name=your-bucket-name"
```

### Python Script
```bash
python scripts/cleanup_role.py --role-name SageMakerFinetuningRole
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review AWS IAM documentation: https://docs.aws.amazon.com/IAM/
3. Review SageMaker documentation: https://docs.aws.amazon.com/sagemaker/
4. Open an issue in the project repository

## References

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [SageMaker Execution Roles](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)
- [Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html)
- [S3 Bucket Policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html)
