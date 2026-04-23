# Quick Reference Guide

## One-Command Setup

### CloudFormation (Recommended)
```bash
aws cloudformation create-stack \
  --stack-name sagemaker-finetuning-role \
  --template-body file://config/aws/cloudformation/sagemaker-role.yaml \
  --parameters ParameterKey=S3BucketName,ParameterValue=YOUR_BUCKET_NAME \
  --capabilities CAPABILITY_NAMED_IAM && \
aws cloudformation wait stack-create-complete --stack-name sagemaker-finetuning-role && \
aws cloudformation describe-stacks --stack-name sagemaker-finetuning-role \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' --output text
```

### Terraform
```bash
cd config/aws/terraform/ && \
terraform init && \
terraform apply -var="s3_bucket_name=YOUR_BUCKET_NAME" -auto-approve && \
terraform output role_arn
```

### Python Script
```bash
python config/aws/scripts/create_iam_role.py --bucket-name YOUR_BUCKET_NAME
```

---

## Common Commands

### Create Role
```bash
# CloudFormation
aws cloudformation create-stack \
  --stack-name sagemaker-finetuning-role \
  --template-body file://config/aws/cloudformation/sagemaker-role.yaml \
  --parameters ParameterKey=S3BucketName,ParameterValue=my-bucket \
  --capabilities CAPABILITY_NAMED_IAM

# Terraform
cd config/aws/terraform/
terraform apply -var="s3_bucket_name=my-bucket"

# Python
python config/aws/scripts/create_iam_role.py --bucket-name my-bucket
```

### Validate Permissions
```bash
python config/aws/scripts/validate_permissions.py \
  --role-arn arn:aws:iam::123456789012:role/SageMakerFinetuningRole
```

### Delete Role
```bash
# CloudFormation
aws cloudformation delete-stack --stack-name sagemaker-finetuning-role

# Terraform
cd config/aws/terraform/
terraform destroy -var="s3_bucket_name=my-bucket"

# Python
python config/aws/scripts/cleanup_role.py --role-name SageMakerFinetuningRole
```

---

## Configuration Update

After creating the role, update `config/pipeline_config.yaml`:

```yaml
aws:
  sagemaker_role_arn: arn:aws:iam::123456789012:role/SageMakerFinetuningRole
  s3_bucket: your-bucket-name
```

---

## Troubleshooting Quick Fixes

### "Access Denied" on S3
```bash
# Check bucket name in policy
aws iam get-role-policy --role-name SageMakerFinetuningRole --policy-name S3AccessPolicy
```

### "Cannot Assume Role"
```bash
# Check trust policy
aws iam get-role --role-name SageMakerFinetuningRole --query 'Role.AssumeRolePolicyDocument'
```

### "Role Already Exists"
```bash
# Use different name
python config/aws/scripts/create_iam_role.py --bucket-name my-bucket --role-name SageMakerRole2
```

---

## Required AWS Permissions (for setup)

To create the IAM role, you need:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:GetRole",
        "iam:TagRole"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Cost Estimates

| Resource | Cost per Hour | Cost per Pipeline Run |
|----------|---------------|----------------------|
| SageMaker Training (ml.g5.2xlarge) | $1.52 | $1.50 - $5.00 |
| SageMaker Endpoint (ml.g5.xlarge) | $1.01 | $1.00 - $2.00 |
| Bedrock API (Claude Sonnet 4) | N/A | $0.50 - $5.00 |
| S3 Storage | $0.023/GB/month | $0.01 - $0.10 |
| CloudWatch Logs | $0.50/GB | $0.01 - $0.05 |
| **Total** | - | **$3.00 - $12.00** |

---

## Security Checklist

- [ ] Role uses least privilege permissions
- [ ] S3 bucket name is specific (not `*`)
- [ ] CloudTrail logging is enabled
- [ ] Budget alerts are configured
- [ ] VPC is enabled (if required)
- [ ] KMS encryption is enabled (if required)
- [ ] Role is tagged appropriately

---

## Support

- **Documentation**: `config/aws/README.md`
- **Permissions Guide**: `config/aws/PERMISSIONS_EXPLAINED.md`
- **AWS IAM Docs**: https://docs.aws.amazon.com/IAM/
- **SageMaker Docs**: https://docs.aws.amazon.com/sagemaker/

---

## File Locations

```
config/aws/
├── README.md                           # Main documentation
├── PERMISSIONS_EXPLAINED.md            # Detailed permission guide
├── QUICK_REFERENCE.md                  # This file
├── policies/
│   ├── trust-policy.json
│   ├── s3-access-policy.json
│   ├── bedrock-access-policy.json
│   ├── cloudwatch-logs-policy.json
│   └── sagemaker-execution-policy.json
├── cloudformation/
│   └── sagemaker-role.yaml
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── README.md
└── scripts/
    ├── create_iam_role.py
    ├── validate_permissions.py
    └── cleanup_role.py
```
