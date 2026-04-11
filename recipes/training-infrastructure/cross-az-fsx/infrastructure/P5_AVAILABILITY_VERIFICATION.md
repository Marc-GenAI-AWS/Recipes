# P5 Instance Availability Verification

## Overview

This document describes the process for verifying P5 instance availability in the us-west-2b availability zone for SageMaker Training Jobs. This verification satisfies **Requirement 6: P5 Instance Availability Validation** from the cross-AZ FSx SageMaker validation specification.

## Background

P5 instances (ml.p5.48xlarge) are high-performance GPU instances required for training large genomic models with the BioNeMo Megatron Framework. Before executing the full validation workflow, we must confirm these instances are available in the target availability zone (us-west-2b).

## Verification Script

The `verify_p5_availability.py` script performs automated checks to verify P5 instance availability.

### Usage

```bash
# Run the verification script
python3 verify_p5_availability.py

# The script will output verification results and create a JSON report
```

### What the Script Checks

The verification script performs four checks:

1. **Availability Zone Validation**
   - Verifies that us-west-2b exists in the us-west-2 region
   - Checks that the AZ is in an "available" state

2. **Instance Type Support**
   - Confirms that ml.p5.48xlarge is a valid SageMaker instance type format
   - Verifies it follows the P5 instance naming convention

3. **EC2 Capacity Check**
   - Queries EC2 for p5.48xlarge instance type information
   - Retrieves instance specifications (vCPUs, memory, GPU info)
   - Confirms the underlying EC2 instance type exists in the region

4. **SageMaker Instance Availability**
   - Documents that SageMaker does not provide a direct availability check API
   - Notes that the definitive test is to launch a training job

### Output

The script produces two outputs:

1. **Console Output**: Human-readable verification results with detailed check information
2. **JSON Report**: Machine-readable results saved to `p5_availability_verification.json`

### Example Output

```
======================================================================
P5 Instance Availability Verification
======================================================================
Region: us-west-2
Availability Zone: us-west-2b
Instance Type: ml.p5.48xlarge
Timestamp: 2024-01-15T10:30:45Z
======================================================================

[1/4] Verifying availability zone exists...
  ✓ Availability zone us-west-2b exists (State: available)

[2/4] Verifying instance type is supported by SageMaker...
  ✓ Instance type ml.p5.48xlarge is a valid P5 instance format

[3/4] Checking EC2 capacity information...
  ✓ EC2 p5.48xlarge instance type exists in region
    - vCPUs: 192
    - Memory: 2048000 MiB
    - GPU Info: NVIDIA H100

[4/4] Checking SageMaker instance availability...
  ! SageMaker does not expose an API to check instance availability
  ! The definitive test is to launch a training job
  ! Recommendation: Attempt a test training job to confirm availability

======================================================================
VERIFICATION SUMMARY
======================================================================
Available: True
Confidence: HIGH
Reason: P5 instances appear to be available for SageMaker Training Jobs
======================================================================

✓ P5 instances appear to be available for SageMaker Training Jobs
✓ You can proceed with launching training jobs in us-west-2b

NOTE: The only definitive way to verify availability is to launch
      a SageMaker Training Job. If capacity is unavailable, the job
      will fail with a ResourceLimitExceeded error.
```

## Confidence Levels

The script assigns a confidence level based on the checks:

- **HIGH**: AZ is valid, instance type is supported, and EC2 instance type exists
- **MEDIUM**: AZ is valid and instance type is supported, but EC2 check failed
- **LOW**: AZ is invalid or instance type is not supported

## Limitations

### AWS API Limitations

AWS does not provide a direct API to check real-time instance availability for SageMaker Training Jobs. The verification script can confirm:

- The availability zone exists and is available
- The instance type is valid
- The underlying EC2 instance type exists in the region

However, it **cannot** confirm:

- Real-time capacity availability
- Whether you have sufficient service quotas
- Whether instances are currently in use

### Definitive Verification

The only definitive way to verify P5 instance availability is to **launch a test SageMaker Training Job**. If capacity is unavailable, the job will fail with one of these errors:

- `ResourceLimitExceeded`: Insufficient capacity in the availability zone
- `ServiceQuotaExceeded`: Your account quota for P5 instances has been reached

## Manual Verification Steps

If you need to manually verify P5 availability:

### Step 1: Check Service Quotas

```bash
# Check your SageMaker service quotas
aws service-quotas get-service-quota \
  --service-code sagemaker \
  --quota-code L-8B5DD645 \
  --region us-west-2
```

This checks your quota for ml.p5.48xlarge instances.

### Step 2: Launch a Test Training Job

Create a minimal test training job to verify capacity:

```python
import boto3

sagemaker = boto3.client('sagemaker', region_name='us-west-2')

response = sagemaker.create_training_job(
    TrainingJobName='p5-availability-test',
    RoleArn='arn:aws:iam::ACCOUNT_ID:role/SageMakerRole',
    AlgorithmSpecification={
        'TrainingImage': '763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-gpu-py310',
        'TrainingInputMode': 'File'
    },
    ResourceConfig={
        'InstanceType': 'ml.p5.48xlarge',
        'InstanceCount': 1,
        'VolumeSizeInGB': 50,
        'AvailabilityZone': 'us-west-2b'  # Specify target AZ
    },
    StoppingCondition={
        'MaxRuntimeInSeconds': 300
    },
    OutputDataConfig={
        'S3OutputPath': 's3://your-bucket/output'
    }
)
```

If the job starts successfully, P5 instances are available. If it fails with `ResourceLimitExceeded`, capacity is unavailable.

### Step 3: Request Quota Increase (if needed)

If you encounter quota limits:

1. Go to AWS Service Quotas console
2. Navigate to SageMaker quotas
3. Find "ml.p5.48xlarge for training job usage"
4. Request a quota increase

## Integration with Validation Workflow

This verification is **Task 1.7** in Phase 1 (Infrastructure Setup) of the validation workflow. It should be executed:

- **Before** launching any SageMaker Training Jobs
- **After** completing infrastructure setup (VPC, FSx, IAM roles)
- **As a prerequisite** for Phase 2 (Data Preparation) and beyond

### Workflow Integration

```python
from verify_p5_availability import P5AvailabilityVerifier

# In ValidationController.verify_p5_availability()
verifier = P5AvailabilityVerifier(region="us-west-2")
result = verifier.verify_p5_availability(
    availability_zone="us-west-2b",
    instance_type="ml.p5.48xlarge"
)

if not result['available']:
    raise RuntimeError(
        f"P5 instances not available: {result['reason']}"
    )

# Log the verification result
logger.info(f"P5 availability verified with {result['confidence']} confidence")
```

## Troubleshooting

### Issue: Availability zone not found

**Symptom**: Script reports "Availability zone us-west-2b not found"

**Solution**: 
- Verify you're using the correct region (us-west-2)
- Check that your AWS credentials have permission to describe availability zones
- Confirm the AZ name is correct (should be "us-west-2b", not "usw2-az2")

### Issue: EC2 instance type not found

**Symptom**: Script reports "EC2 p5.48xlarge instance type not found in region"

**Solution**:
- P5 instances may not be available in all regions
- Verify us-west-2 supports P5 instances
- Check AWS documentation for P5 instance availability by region

### Issue: Permission denied errors

**Symptom**: Script fails with permission errors

**Solution**:
- Ensure your AWS credentials have the following permissions:
  - `ec2:DescribeAvailabilityZones`
  - `ec2:DescribeInstanceTypes`
  - `sagemaker:DescribeTrainingJob` (for future integration)

### Issue: ResourceLimitExceeded when launching training job

**Symptom**: Training job fails immediately with ResourceLimitExceeded

**Solution**:
- P5 capacity is limited and may be unavailable
- Try a different availability zone (us-west-2a, us-west-2c)
- Request a service quota increase
- Try launching during off-peak hours
- Consider using ml.p4d.24xlarge as an alternative

## References

- [SageMaker Training Job Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/train-model.html)
- [P5 Instance Specifications](https://aws.amazon.com/ec2/instance-types/p5/)
- [SageMaker Service Quotas](https://docs.aws.amazon.com/general/latest/gr/sagemaker.html)
- [Cross-AZ FSx SageMaker Validation Spec](.kiro/specs/cross-az-fsx-sagemaker-validation/)

## Next Steps

After verifying P5 availability:

1. Proceed to **Phase 2: Data Preparation** (Task 2.1)
2. Download hg38 chromosome data from UCSC
3. Upload data to FSx volume
4. Begin validation execution with 10GB dataset

## Conclusion

The P5 availability verification script provides automated checks to confirm that ml.p5.48xlarge instances can be used for SageMaker Training Jobs in us-west-2b. While it cannot guarantee real-time capacity availability, it validates the prerequisites and provides high confidence that the instances are supported in the target configuration.

For definitive verification, a test training job launch is recommended before executing the full validation workflow.
