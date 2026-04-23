# Terraform Configuration for SageMaker IAM Role

This directory contains Terraform configuration to create an IAM role for the SageMaker LLM finetuning pipeline with minimal required permissions.

## Prerequisites

1. **Terraform**: Install Terraform >= 1.0
   ```bash
   # macOS
   brew install terraform
   
   # Windows
   choco install terraform
   
   # Linux
   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
   unzip terraform_1.6.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```

2. **AWS CLI**: Configure AWS credentials
   ```bash
   aws configure
   ```

3. **S3 Bucket**: Create an S3 bucket for training data (or use existing)
   ```bash
   aws s3 mb s3://your-finetuning-bucket
   ```

## Quick Start

### 1. Initialize Terraform

```bash
cd config/aws/terraform/
terraform init
```

### 2. Review the Plan

```bash
terraform plan -var="s3_bucket_name=your-finetuning-bucket"
```

### 3. Apply the Configuration

```bash
terraform apply -var="s3_bucket_name=your-finetuning-bucket"
```

Type `yes` when prompted to confirm.

### 4. Get the Role ARN

```bash
terraform output role_arn
```

Copy this ARN and update your `config/pipeline_config.yaml`:

```yaml
aws:
  sagemaker_role_arn: <paste-role-arn-here>
  s3_bucket: your-finetuning-bucket
```

## Configuration Options

### Basic Configuration

```bash
terraform apply \
  -var="s3_bucket_name=your-finetuning-bucket" \
  -var="role_name=SageMakerFinetuningRole"
```

### With VPC Access

If you need SageMaker to run in a VPC:

```bash
terraform apply \
  -var="s3_bucket_name=your-finetuning-bucket" \
  -var="enable_vpc_access=true"
```

### With KMS Encryption

If you use KMS encryption for S3:

```bash
terraform apply \
  -var="s3_bucket_name=your-finetuning-bucket" \
  -var="enable_kms_encryption=true" \
  -var="kms_key_arn=arn:aws:kms:us-east-1:123456789012:key/your-key-id"
```

### Using a Variables File

Create a `terraform.tfvars` file:

```hcl
aws_region           = "us-east-1"
role_name            = "SageMakerFinetuningRole"
s3_bucket_name       = "your-finetuning-bucket"
enable_vpc_access    = false
enable_kms_encryption = false

tags = {
  Environment = "Production"
  Team        = "ML-Engineering"
}
```

Then apply:

```bash
terraform apply
```

## Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `aws_region` | AWS region for resources | `us-east-1` | No |
| `role_name` | Name for the SageMaker execution role | `SageMakerFinetuningRole` | No |
| `s3_bucket_name` | S3 bucket for training data and artifacts | - | **Yes** |
| `enable_vpc_access` | Enable VPC access for SageMaker | `false` | No |
| `enable_kms_encryption` | Enable KMS encryption for S3 | `false` | No |
| `kms_key_arn` | ARN of KMS key (if encryption enabled) | `""` | No |
| `tags` | Additional tags for resources | `{}` | No |

## Outputs

After applying, Terraform provides these outputs:

- `role_arn`: ARN of the created IAM role
- `role_name`: Name of the IAM role
- `role_id`: Unique ID of the IAM role
- `s3_bucket_name`: Configured S3 bucket name
- `configuration_instructions`: Next steps for pipeline setup

View outputs:

```bash
terraform output
terraform output role_arn
terraform output -json
```

## State Management

### Local State (Default)

By default, Terraform stores state locally in `terraform.tfstate`. This is fine for individual use but not recommended for teams.

### Remote State (Recommended for Teams)

Configure S3 backend for shared state:

Create `backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "sagemaker-role/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

Initialize with backend:

```bash
terraform init -backend-config="backend.tf"
```

## Validation

After creating the role, validate permissions:

```bash
# Get the role ARN
ROLE_ARN=$(terraform output -raw role_arn)

# Run validation script
python ../scripts/validate_permissions.py --role-arn $ROLE_ARN
```

## Updating the Role

To modify the role:

1. Edit the Terraform files
2. Review changes: `terraform plan`
3. Apply changes: `terraform apply`

Terraform will show what will change before applying.

## Destroying Resources

To remove the IAM role:

```bash
terraform destroy -var="s3_bucket_name=your-finetuning-bucket"
```

**Warning**: This will delete the IAM role. Ensure no SageMaker jobs are using it.

## Troubleshooting

### Error: Role Already Exists

If the role name is already taken:

```bash
terraform apply -var="role_name=SageMakerFinetuningRole2"
```

### Error: Insufficient Permissions

Ensure your AWS credentials have permissions to:
- Create IAM roles
- Attach IAM policies
- Tag IAM resources

Required IAM permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:TagRole"
      ],
      "Resource": "*"
    }
  ]
}
```

### Error: Invalid Bucket Name

Bucket names must:
- Be lowercase
- Start and end with alphanumeric
- Use only alphanumeric and hyphens
- Be 3-63 characters

### State Lock Issues

If Terraform state is locked:

```bash
# Force unlock (use with caution)
terraform force-unlock <lock-id>
```

## Best Practices

1. **Use Remote State**: Store state in S3 with DynamoDB locking for teams
2. **Version Control**: Commit Terraform files to git (exclude `terraform.tfstate`)
3. **Variables File**: Use `terraform.tfvars` for environment-specific values
4. **Plan Before Apply**: Always run `terraform plan` before `terraform apply`
5. **Tag Resources**: Use tags for cost tracking and organization
6. **Validate**: Run validation script after creating role

## Examples

### Development Environment

```bash
terraform apply \
  -var="s3_bucket_name=dev-finetuning-bucket" \
  -var="role_name=SageMakerFinetuningRole-Dev" \
  -var="tags={Environment=Development,Team=ML}"
```

### Production Environment

```bash
terraform apply \
  -var="s3_bucket_name=prod-finetuning-bucket" \
  -var="role_name=SageMakerFinetuningRole-Prod" \
  -var="enable_kms_encryption=true" \
  -var="kms_key_arn=arn:aws:kms:us-east-1:123456789012:key/prod-key" \
  -var="tags={Environment=Production,Team=ML,CostCenter=Engineering}"
```

## Additional Resources

- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [SageMaker Execution Roles](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)
