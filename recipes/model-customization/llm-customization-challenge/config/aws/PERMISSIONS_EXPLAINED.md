# IAM Permissions Explained

This document explains each permission required by the SageMaker execution role and why it's needed for the LLM finetuning pipeline.

## Overview

The IAM role follows the **principle of least privilege**, granting only the minimum permissions necessary for the pipeline to function. Each permission is scoped to specific resources where possible.

## Permission Categories

### 1. S3 Permissions

#### Why S3 Access is Needed
The pipeline stores training data, model artifacts, and results in S3. SageMaker needs to read training data and write model outputs.

#### Required Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `s3:ListBucket` | `arn:aws:s3:::bucket-name` | List objects in the bucket to verify training data exists |
| `s3:GetBucketLocation` | `arn:aws:s3:::bucket-name` | Determine bucket region for cross-region operations |
| `s3:GetObject` | `arn:aws:s3:::bucket-name/*` | Read training data (JSONL files) for model training |
| `s3:PutObject` | `arn:aws:s3:::bucket-name/*` | Write model artifacts after training completes |
| `s3:DeleteObject` | `arn:aws:s3:::bucket-name/*` | Clean up temporary files and old artifacts |
| `s3:ListAllMyBuckets` | `*` | List available buckets (used for validation) |

#### Security Notes
- Permissions are scoped to a specific bucket (not `*`)
- Object-level permissions use bucket prefix (`bucket-name/*`)
- No permissions to modify bucket policies or ACLs
- No permissions to delete buckets

#### Example Use Cases
- **Training**: SageMaker reads `s3://bucket/training_data/use_case_iter1.jsonl`
- **Model Storage**: SageMaker writes `s3://bucket/models/model.tar.gz`
- **Cleanup**: Pipeline deletes `s3://bucket/temp/training_job_123/`

---

### 2. SageMaker Permissions

#### Why SageMaker Access is Needed
The pipeline creates training jobs, deploys models to endpoints, and invokes endpoints for inference.

#### Training Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `sagemaker:CreateTrainingJob` | `training-job/*` | Start finetuning jobs for Llama 3.2 3B |
| `sagemaker:DescribeTrainingJob` | `training-job/*` | Monitor training progress and status |
| `sagemaker:StopTrainingJob` | `training-job/*` | Cancel training if needed |
| `sagemaker:ListTrainingJobs` | `training-job/*` | List jobs for tracking and cleanup |

**Use Case**: Create a training job that finetunes Llama 3.2 3B on synthetic data for 5 epochs.

#### Model Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `sagemaker:CreateModel` | `model/*` | Create model resource from training artifacts |
| `sagemaker:DescribeModel` | `model/*` | Get model details for deployment |
| `sagemaker:DeleteModel` | `model/*` | Clean up models after pipeline completion |
| `sagemaker:ListModels` | `model/*` | List models for tracking |

**Use Case**: Create a model resource pointing to the trained model artifacts in S3.

#### Endpoint Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `sagemaker:CreateEndpointConfig` | `endpoint-config/*` | Configure endpoint instance type and count |
| `sagemaker:DescribeEndpointConfig` | `endpoint-config/*` | Get endpoint configuration details |
| `sagemaker:DeleteEndpointConfig` | `endpoint-config/*` | Clean up endpoint configs |
| `sagemaker:CreateEndpoint` | `endpoint/*` | Deploy model to a real-time endpoint |
| `sagemaker:DescribeEndpoint` | `endpoint/*` | Monitor endpoint status |
| `sagemaker:DeleteEndpoint` | `endpoint/*` | Clean up endpoints to save costs |
| `sagemaker:UpdateEndpoint` | `endpoint/*` | Update endpoint with new model version |
| `sagemaker:InvokeEndpoint` | `endpoint/*` | Generate predictions from deployed model |
| `sagemaker:ListEndpoints` | `endpoint/*` | List endpoints for tracking |

**Use Case**: Deploy finetuned model to `ml.g5.xlarge` endpoint and invoke it for test questions.

#### JumpStart Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `sagemaker:ListModelPackages` | `*` | List available JumpStart models |
| `sagemaker:DescribeModelPackage` | `*` | Get details about Llama 3.2 3B model package |

**Use Case**: Access pre-configured Llama 3.2 3B model from SageMaker JumpStart.

#### Security Notes
- All permissions scoped to account-specific resources
- No permissions to modify SageMaker domain or user profiles
- No permissions to access other accounts' resources
- Endpoint invocation limited to account's endpoints

---

### 3. Bedrock Permissions

#### Why Bedrock Access is Needed
The pipeline uses Claude Sonnet 4 via Bedrock for:
1. Generating synthetic training data
2. Judging model responses (comparing finetuned vs baseline)
3. Self-improvement (analyzing failures and improving prompts)

#### Required Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `bedrock:InvokeModel` | `foundation-model/anthropic.claude-sonnet-4-*` | Call Claude Sonnet 4 for data generation and judging |
| `bedrock:InvokeModelWithResponseStream` | `foundation-model/anthropic.claude-sonnet-4-*` | Stream responses for long generations |
| `bedrock:GetFoundationModel` | `*` | Get model details (context window, pricing) |
| `bedrock:ListFoundationModels` | `*` | List available models for validation |

#### Security Notes
- Permissions scoped to Claude models only (not all Bedrock models)
- Includes Claude 3 family for backward compatibility
- No permissions to create custom models or fine-tune Bedrock models
- No permissions to modify model access or pricing

#### Example Use Cases
- **Data Generation**: Call Claude Sonnet 4 to generate 1000 training examples
- **Judging**: Call Claude Sonnet 4 to compare finetuned vs baseline responses
- **Self-Improvement**: Call Claude Sonnet 4 to analyze failures and suggest prompt improvements

#### Cost Implications
- Claude Sonnet 4: ~$3 per 1M input tokens, ~$15 per 1M output tokens
- Typical pipeline run: 100K-500K tokens (~$0.50-$5.00)
- Set budget alerts in AWS Budgets to monitor costs

---

### 4. CloudWatch Permissions

#### Why CloudWatch Access is Needed
The pipeline logs all operations for debugging, monitoring, and audit trails. SageMaker also writes training logs to CloudWatch.

#### Required Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `logs:CreateLogGroup` | `/aws/sagemaker/*`, `FinetuningPipeline/*` | Create log groups for training jobs and pipeline |
| `logs:CreateLogStream` | `/aws/sagemaker/*`, `FinetuningPipeline/*` | Create log streams for each execution |
| `logs:PutLogEvents` | `/aws/sagemaker/*`, `FinetuningPipeline/*` | Write log messages |
| `logs:DescribeLogStreams` | `/aws/sagemaker/*`, `FinetuningPipeline/*` | List log streams for monitoring |
| `cloudwatch:PutMetricData` | `*` (with namespace condition) | Publish custom metrics |

#### Namespace Restrictions
Metrics can only be published to:
- `AWS/SageMaker` - SageMaker service metrics
- `FinetuningPipeline/Dev` - Development environment metrics
- `FinetuningPipeline/Prod` - Production environment metrics

#### Security Notes
- Log groups scoped to SageMaker and pipeline-specific groups
- No permissions to read logs from other services
- No permissions to delete log groups
- Metrics restricted to specific namespaces

#### Example Use Cases
- **Training Logs**: SageMaker writes training progress to `/aws/sagemaker/TrainingJobs/job-name`
- **Pipeline Logs**: Pipeline writes execution logs to `FinetuningPipeline/Prod/use-case-name`
- **Metrics**: Publish win rate, training time, and cost metrics

---

### 5. ECR Permissions

#### Why ECR Access is Needed
SageMaker training and inference containers are stored in Amazon ECR (Elastic Container Registry). The role needs to pull these containers.

#### Required Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `ecr:GetAuthorizationToken` | `*` | Authenticate to ECR to pull containers |
| `ecr:BatchCheckLayerAvailability` | `*` | Check if container layers are available |
| `ecr:GetDownloadUrlForLayer` | `*` | Get URLs to download container layers |
| `ecr:BatchGetImage` | `*` | Pull container images |

#### Security Notes
- Read-only access to ECR
- No permissions to push images or modify repositories
- Required for SageMaker to function (not optional)

#### Example Use Cases
- **Training**: Pull Llama 3.2 3B training container from ECR
- **Inference**: Pull inference container for endpoint deployment

---

### 6. VPC Permissions (Optional)

#### Why VPC Access is Needed
If you run SageMaker in a VPC for network isolation, the role needs to create network interfaces.

#### Required Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `ec2:CreateNetworkInterface` | `*` | Create ENI for SageMaker in VPC |
| `ec2:CreateNetworkInterfacePermission` | `*` | Grant permissions on ENI |
| `ec2:DeleteNetworkInterface` | `*` | Clean up ENI after job completes |
| `ec2:DeleteNetworkInterfacePermission` | `*` | Remove ENI permissions |
| `ec2:DescribeNetworkInterfaces` | `*` | List ENIs for monitoring |
| `ec2:DescribeVpcs` | `*` | Get VPC details |
| `ec2:DescribeDhcpOptions` | `*` | Get DHCP configuration |
| `ec2:DescribeSubnets` | `*` | Get subnet details |
| `ec2:DescribeSecurityGroups` | `*` | Get security group details |

#### Security Notes
- Only needed if using VPC configuration
- Permissions are broad (`*`) because ENIs can be in any VPC
- Consider using VPC endpoints to avoid internet access

#### When to Enable
- ✅ Enable if: You need network isolation or private connectivity
- ❌ Disable if: You're using default SageMaker networking (simpler, no VPC costs)

---

### 7. KMS Permissions (Optional)

#### Why KMS Access is Needed
If you encrypt S3 buckets with customer-managed KMS keys, the role needs to decrypt/encrypt data.

#### Required Permissions

| Permission | Resource | Why Needed |
|------------|----------|------------|
| `kms:Decrypt` | `key/key-id` | Decrypt training data from S3 |
| `kms:Encrypt` | `key/key-id` | Encrypt model artifacts to S3 |
| `kms:GenerateDataKey` | `key/key-id` | Generate data encryption keys |
| `kms:DescribeKey` | `key/key-id` | Get key metadata |

#### Security Notes
- Permissions scoped to specific KMS key ARN
- Only needed if using customer-managed keys (not AWS-managed keys)
- Key policy must also allow SageMaker service to use the key

#### When to Enable
- ✅ Enable if: You use customer-managed KMS keys for S3 encryption
- ❌ Disable if: You use AWS-managed keys or no encryption (simpler)

---

## Permission Validation

### How to Validate Permissions

Use the validation script to check all permissions:

```bash
python config/aws/scripts/validate_permissions.py --role-arn arn:aws:iam::123456789012:role/SageMakerFinetuningRole
```

The script checks:
- ✓ Role exists and is assumable by SageMaker
- ✓ S3 read/write permissions
- ✓ SageMaker training and deployment permissions
- ✓ Bedrock model invocation permissions
- ✓ CloudWatch logging permissions

### Common Permission Issues

#### Issue: "Access Denied" on S3
**Cause**: Bucket name in policy doesn't match actual bucket
**Fix**: Update S3 policy with correct bucket name

#### Issue: "Access Denied" on SageMaker Training
**Cause**: Missing `sagemaker:CreateTrainingJob` permission
**Fix**: Ensure SageMaker execution policy is attached

#### Issue: "Access Denied" on Bedrock
**Cause**: Bedrock not enabled in region or model ID mismatch
**Fix**: Enable Bedrock in AWS console and verify model ID

#### Issue: "Cannot Assume Role"
**Cause**: Trust policy doesn't include SageMaker service
**Fix**: Update trust policy to allow `sagemaker.amazonaws.com`

---

## Security Best Practices

### 1. Scope Permissions to Specific Resources
✅ **Good**: `arn:aws:s3:::my-specific-bucket/*`
❌ **Bad**: `arn:aws:s3:::*/*`

### 2. Use Separate Roles for Dev and Prod
- Dev role: Broader permissions for experimentation
- Prod role: Minimal permissions, audited regularly

### 3. Enable CloudTrail Logging
Monitor all API calls made by the role:
```bash
aws cloudtrail lookup-events --lookup-attributes AttributeKey=Username,AttributeValue=SageMakerFinetuningRole
```

### 4. Set Up Budget Alerts
Prevent unexpected costs:
```bash
aws budgets create-budget --account-id 123456789012 --budget file://budget.json
```

### 5. Rotate Credentials Regularly
If using IAM users (not recommended), rotate access keys every 90 days.

### 6. Use Permission Boundaries
If your organization requires permission boundaries:
```bash
aws iam put-role-permissions-boundary --role-name SageMakerFinetuningRole --permissions-boundary arn:aws:iam::123456789012:policy/OrgBoundary
```

### 7. Review Permissions Quarterly
Schedule regular reviews to remove unused permissions.

---

## Cost Optimization

### Minimize Costs with Proper Permissions

1. **Enable Cleanup**: Grant `sagemaker:DeleteEndpoint` to avoid idle endpoint costs
2. **Use Spot Instances**: Grant `sagemaker:CreateTrainingJob` with spot instance support
3. **Set Retention Policies**: Grant `s3:DeleteObject` to clean up old artifacts
4. **Monitor Usage**: Grant `cloudwatch:PutMetricData` to track costs

### Estimated Costs by Permission Category

| Category | Typical Cost per Pipeline Run |
|----------|-------------------------------|
| S3 Storage | $0.01 - $0.10 |
| SageMaker Training | $1.00 - $5.00 |
| SageMaker Endpoints | $1.00 - $2.00 per hour |
| Bedrock API | $0.50 - $5.00 |
| CloudWatch Logs | $0.01 - $0.05 |
| **Total** | **$2.50 - $12.00 per run** |

---

## Compliance and Audit

### Audit Trail
All actions are logged to CloudTrail:
- Who assumed the role
- What actions were performed
- When actions occurred
- Which resources were accessed

### Compliance Requirements
The role configuration supports:
- **SOC 2**: Least privilege, audit logging
- **HIPAA**: Encryption at rest (KMS), VPC isolation
- **PCI DSS**: Network isolation, access logging
- **GDPR**: Data encryption, access controls

### Audit Checklist
- [ ] Role follows least privilege principle
- [ ] All permissions are documented and justified
- [ ] CloudTrail logging is enabled
- [ ] Regular permission reviews are scheduled
- [ ] Unused permissions are removed
- [ ] Budget alerts are configured

---

## Troubleshooting

### Debug Permission Issues

1. **Check CloudTrail for Denied Actions**
   ```bash
   aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=AccessDenied
   ```

2. **Simulate Policy**
   ```bash
   aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::123456789012:role/SageMakerFinetuningRole --action-names sagemaker:CreateTrainingJob
   ```

3. **Review IAM Policy Simulator**
   https://policysim.aws.amazon.com/

4. **Enable Debug Logging**
   Set `AWS_LOG_LEVEL=debug` to see detailed API calls

---

## Additional Resources

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [SageMaker Security](https://docs.aws.amazon.com/sagemaker/latest/dg/security.html)
- [Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html)
- [S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [CloudWatch Logs Security](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/auth-and-access-control-cwl.html)
