# SageMaker Cross-AZ Validation Quick Start

Quick guide to launch a SageMaker training job that validates cross-AZ FSx access.

## Prerequisites

- ✅ FSx volume deployed (fs-04b3f909e86004fc2)
- ✅ Data uploaded to FSx (10GB job should be complete or nearly complete)
- ✅ Docker installed
- ✅ AWS CLI configured
- ✅ Python 3.8+ with boto3

## Step 1: Build and Push Docker Container

The training job runs in a Docker container that mounts the FSx volume and validates access.

**On Windows (PowerShell):**
```powershell
cd validation/training_container
.\build_and_push.ps1
```

**On Linux/Mac:**
```bash
cd validation/training_container
chmod +x build_and_push.sh
./build_and_push.sh
```

This will:
1. Create an ECR repository named `fsx-validation`
2. Build the Docker image
3. Push it to ECR

**Expected time:** 2-5 minutes

## Step 2: Launch Training Job

Once the container is pushed and your 10GB data prep job is complete, launch the validation job:

```bash
cd validation
python launch_test_training_job.py \
  --job-name test-cross-az-10gb \
  --fsx-file-system-id fs-04b3f909e86004fc2 \
  --data-subdir phase_10gb \
  --target-az us-west-2b \
  --instance-type ml.m5.xlarge \
  --wait
```

**Parameters:**
- `--job-name`: Unique name for this training job
- `--fsx-file-system-id`: Your FSx file system ID
- `--data-subdir`: Where your data is (phase_10gb, phase_100gb, etc.)
- `--target-az`: AZ for training job (different from FSx AZ for cross-AZ test)
- `--instance-type`: SageMaker instance type (ml.m5.xlarge is cheap for testing)
- `--wait`: Wait for job completion (optional)

## Step 3: Monitor Progress

The script will show real-time status updates:

```
2024-04-10 15:30:00 - INFO - Launching validation job: test-cross-az-10gb
2024-04-10 15:30:01 - INFO - FSx AZ: us-west-2a
2024-04-10 15:30:01 - INFO - FSx SVM DNS: svm-xxxxx.fs-xxxxx.fsx.us-west-2.amazonaws.com
2024-04-10 15:30:01 - INFO - Target AZ: us-west-2b
2024-04-10 15:30:02 - INFO - ✓ Training job launched: test-cross-az-10gb
2024-04-10 15:30:02 - INFO - Waiting for job completion: test-cross-az-10gb
2024-04-10 15:30:32 - INFO - Status: InProgress | Secondary: Starting | Elapsed: 0.5 min
2024-04-10 15:31:02 - INFO - Status: InProgress | Secondary: Training | Elapsed: 1.0 min
...
```

## What the Training Job Does

The training job will:

1. **Mount FSx volume** (cross-AZ from us-west-2a to us-west-2b)
   - Measures mount establishment time
   - Verifies mount accessibility

2. **List data files** in the specified subdirectory
   - Confirms data is accessible
   - Shows file sizes

3. **Measure read performance**
   - Reads files from FSx
   - Calculates throughput (MB/s)

4. **Measure network latency**
   - Tests small read operations
   - Calculates min/avg/p95/p99/max latency

5. **Publish metrics to CloudWatch**
   - Mount time
   - Read throughput
   - Network latency

## Expected Results

**For 10GB cross-AZ test:**
- Mount time: 5-15 seconds
- Read throughput: 100-800 MB/s (depending on FSx throughput capacity)
- Network latency: 0.5-2ms (cross-AZ)
- Total job duration: 5-10 minutes
- Cost: ~$0.05 (ml.m5.xlarge for 10 minutes)

## View Results

**Check CloudWatch Logs:**
```bash
aws logs tail /aws/sagemaker/TrainingJobs --follow --region us-west-2 --log-stream-name-prefix test-cross-az-10gb
```

**Check CloudWatch Metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace CrossAZValidation \
  --metric-name ReadThroughput \
  --dimensions Name=CrossAZ,Value=True Name=DataVolume,Value=phase_10gb \
  --start-time 2024-04-10T00:00:00Z \
  --end-time 2024-04-10T23:59:59Z \
  --period 300 \
  --statistics Average \
  --region us-west-2
```

**Check SageMaker Console:**
1. Go to SageMaker Console → Training Jobs
2. Find your job: `test-cross-az-10gb`
3. View logs, metrics, and status

## Troubleshooting

### "Training image not found"

The Docker container hasn't been pushed to ECR yet. Run Step 1 first.

### "No subnet found in AZ us-west-2b"

Your VPC doesn't have a subnet in us-west-2b. Check your network stack:
```bash
aws ec2 describe-subnets --filters "Name=vpc-id,Values=YOUR_VPC_ID" --region us-west-2
```

### "Mount failed"

Check security groups allow NFS traffic (port 2049) between the SageMaker subnet and FSx security group.

### "No data files found"

The 10GB data prep job hasn't completed yet, or the data is in a different subdirectory. Check:
```bash
# List what's on FSx (from an EC2 instance in same VPC)
ls -lh /mnt/fsx/
```

## Next Steps

After successful 10GB validation:

1. **Run 100GB validation** (when data prep completes):
   ```bash
   python launch_test_training_job.py \
     --job-name test-cross-az-100gb \
     --fsx-file-system-id fs-04b3f909e86004fc2 \
     --data-subdir phase_100gb \
     --target-az us-west-2b
   ```

2. **Compare same-AZ vs cross-AZ performance**:
   ```bash
   # Same-AZ test (training in us-west-2a, same as FSx)
   python launch_test_training_job.py \
     --job-name test-same-az-10gb \
     --fsx-file-system-id fs-04b3f909e86004fc2 \
     --data-subdir phase_10gb \
     --target-az us-west-2a
   ```

3. **Test with larger instance** (closer to production):
   ```bash
   python launch_test_training_job.py \
     --job-name test-cross-az-10gb-large \
     --fsx-file-system-id fs-04b3f909e86004fc2 \
     --data-subdir phase_10gb \
     --target-az us-west-2b \
     --instance-type ml.p4d.24xlarge  # P4 instance for testing
   ```

4. **Integrate BioNeMo** (Phase 4 of the spec)
   - Replace validation script with actual BioNeMo training
   - Use NGC BioNeMo container
   - Configure for genomic data

## Cost Breakdown

**Per validation run:**
- ml.m5.xlarge: $0.269/hour
- Typical duration: 5-10 minutes
- Cost per run: ~$0.02-$0.05

**Cross-AZ data transfer:**
- $0.01/GB
- 10GB test: $0.10
- 100GB test: $1.00
- 2TB test: $20.00

**Total for full validation (10GB-2TB):**
- Compute: ~$0.50
- Data transfer: ~$21.10
- **Total: ~$21.60**

Much cheaper than replicating 800TB across AZs ($160,000/month savings)!

## Summary

This quick validation proves:
- ✅ Cross-AZ FSx mount works from SageMaker
- ✅ Data is accessible and readable
- ✅ Performance is measurable
- ✅ Cost is minimal for testing

You're now ready to scale up to larger datasets and eventually integrate BioNeMo training!
