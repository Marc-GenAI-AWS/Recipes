# EC2 Data Preparation Quick Start Guide

Get started with EC2-based data preparation in 5 minutes.

## Prerequisites

1. AWS account with appropriate permissions
2. FSx NetApp ONTAP file system deployed (from Task 1)
3. Python 3.8+ with boto3 installed
4. AWS credentials configured

## Quick Start

### Step 1: Install Dependencies

```bash
pip install boto3
```

### Step 2: Get Your FSx File System ID

```bash
# List FSx file systems
aws fsx describe-file-systems --region us-west-2

# Note the FileSystemId (e.g., fs-0a1b2c3d4e5f6g7h8)
```

### Step 3: Prepare Your First Dataset (10GB)

```bash
cd infrastructure

python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-YOUR-FILE-SYSTEM-ID \
    --volume-size 10GB \
    --chromosomes chr1 chr2 \
    --dest-subdir phase_10gb
```

That's it! The script will:
1. Launch an EC2 instance in the same AZ as your FSx volume
2. Download chr1 and chr2 from UCSC
3. Upload to FSx with integrity verification
4. Terminate the instance automatically

### Step 4: Check Results

The script outputs progress in real-time. When complete, you'll see:

```
========================================
Dataset Preparation Complete
  Volume size: 10GB
  Destination: phase_10gb
  Duration: 30.5 minutes
========================================
```

### Step 5: Verify Data on FSx

Mount your FSx volume locally and check the data:

```bash
# Mount FSx (replace with your SVM DNS name)
sudo mount -t nfs svm-xxxxx.fs-xxxxx.fsx.us-west-2.amazonaws.com:/genomics /mnt/fsx

# Check uploaded data
ls -lh /mnt/fsx/phase_10gb/

# Check logs
cat /mnt/fsx/phase_10gb/logs/validation_report.json
```

## Common Use Cases

### Prepare 100GB Dataset

```bash
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-YOUR-FILE-SYSTEM-ID \
    --volume-size 100GB \
    --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 \
    --dest-subdir phase_100gb \
    --max-runtime-hours 3
```

### Prepare 500GB Dataset

```bash
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-YOUR-FILE-SYSTEM-ID \
    --volume-size 500GB \
    --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 chr11 chr12 chr13 chr14 chr15 chr16 chr17 chr18 chr19 chr20 chr21 chr22 chrX \
    --dest-subdir phase_500gb \
    --max-runtime-hours 6
```

### Keep Instance Running (for Debugging)

```bash
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-YOUR-FILE-SYSTEM-ID \
    --volume-size 10GB \
    --chromosomes chr1 chr2 \
    --dest-subdir phase_10gb \
    --no-auto-terminate
```

### Save Results to File

```bash
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-YOUR-FILE-SYSTEM-ID \
    --volume-size 100GB \
    --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 \
    --dest-subdir phase_100gb \
    --output results_100gb.json
```

## Cost Estimation

Before preparing large datasets, estimate costs:

```bash
python example_ec2_data_prep_workflow.py --cost-comparison
```

Output:
```
10GB Dataset:
  Preparation time: 0.5 hours
  EC2 cost: $0.34
  Cross-AZ cost: $0.10
  Savings: -$0.24 (-240.0%)
  Recommendation: Use direct transfer

100GB Dataset:
  Preparation time: 1.0 hours
  EC2 cost: $0.68
  Cross-AZ cost: $1.02
  Savings: $0.34 (33.3%)
  Recommendation: Use EC2

500GB Dataset:
  Preparation time: 2.0 hours
  EC2 cost: $1.36
  Cross-AZ cost: $5.12
  Savings: $3.76 (73.4%)
  Recommendation: Use EC2

1024GB Dataset:
  Preparation time: 3.0 hours
  EC2 cost: $2.04
  Cross-AZ cost: $10.24
  Savings: $8.20 (80.1%)
  Recommendation: Use EC2

2048GB Dataset:
  Preparation time: 4.0 hours
  EC2 cost: $2.72
  Cross-AZ cost: $20.48
  Savings: $17.76 (86.7%)
  Recommendation: Use EC2
```

**Recommendation**: Use EC2 for datasets ≥100GB for cost savings.

## Monitoring Progress

### Check Instance Status

```bash
# Get instance ID from script output
python ec2_data_prep_manager.py status --instance-id i-xxxxx
```

### View Console Output

```bash
python ec2_data_prep_manager.py console --instance-id i-xxxxx
```

### Check Logs on FSx

```bash
# Mount FSx locally
sudo mount -t nfs svm-xxxxx.fs-xxxxx.fsx.us-west-2.amazonaws.com:/genomics /mnt/fsx

# View logs
tail -f /mnt/fsx/phase_10gb/logs/data-prep.log
cat /mnt/fsx/phase_10gb/logs/download.log
cat /mnt/fsx/phase_10gb/logs/upload.log
cat /mnt/fsx/phase_10gb/logs/validation.log
```

## Troubleshooting

### Instance Won't Start

**Problem**: Instance launch fails

**Solution**:
1. Check AWS service limits for EC2 instances
2. Verify subnet and security group exist
3. Check IAM permissions

### Mount Fails

**Problem**: FSx mount fails on EC2 instance

**Solution**:
1. Verify FSx SVM DNS name is correct
2. Check security group allows NFS (port 2049)
3. Ensure FSx volume is available
4. Check console output: `python ec2_data_prep_manager.py console --instance-id i-xxxxx`

### Download Slow

**Problem**: Chromosome download is very slow

**Solution**:
1. Check UCSC server status
2. Verify EC2 instance has internet access
3. Consider using larger instance type
4. Check network connectivity

### Upload Slow

**Problem**: Upload to FSx is slow

**Solution**:
1. Check FSx throughput capacity
2. Monitor FSx performance metrics in CloudWatch
3. Consider increasing FSx throughput
4. Verify same-AZ placement

### Validation Fails

**Problem**: Data integrity validation fails

**Solution**:
1. Check validation logs: `/mnt/fsx/phase_10gb/logs/validation.log`
2. Review checksum mismatches
3. Re-run preparation with fresh download
4. Check FSx volume health

### Timeout

**Problem**: Preparation exceeds maximum runtime

**Solution**:
1. Increase `--max-runtime-hours` parameter
2. Use larger instance type for faster processing
3. Check for network issues
4. Review console output for errors

## Advanced Usage

### Use Custom Scripts from S3

```bash
# Upload scripts to S3
aws s3 sync validation/data_preparation/ s3://my-bucket/scripts/

# Use in preparation
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-YOUR-FILE-SYSTEM-ID \
    --volume-size 10GB \
    --chromosomes chr1 chr2 \
    --dest-subdir phase_10gb \
    --s3-scripts-bucket my-bucket/scripts
```

### Prepare Multiple Datasets Sequentially

```bash
python example_ec2_data_prep_workflow.py \
    --fsx-file-system-id fs-YOUR-FILE-SYSTEM-ID \
    --dataset-size all
```

This prepares 10GB, 100GB, and 500GB datasets sequentially.

### Manual Instance Management

For more control, use the low-level manager:

```bash
# Launch instance
python ec2_data_prep_manager.py launch \
    --subnet-id subnet-xxxxx \
    --security-group-id sg-xxxxx \
    --user-data user_data_script.sh \
    --instance-name my-data-prep

# Monitor status
python ec2_data_prep_manager.py status --instance-id i-xxxxx

# Get console output
python ec2_data_prep_manager.py console --instance-id i-xxxxx

# Terminate when done
python ec2_data_prep_manager.py terminate --instance-id i-xxxxx --wait
```

## Best Practices

1. **Start Small**: Test with 10GB dataset first
2. **Monitor Costs**: Use cost estimation before large datasets
3. **Check Logs**: Review logs after each preparation
4. **Auto-Terminate**: Enable auto-termination to minimize costs
5. **Same AZ**: Ensure EC2 and FSx are in same AZ
6. **Set Timeouts**: Configure appropriate max runtime
7. **Save Results**: Use `--output` to save results to file
8. **Verify Data**: Always check validation reports

## Next Steps

1. **Prepare validation datasets**: Use this infrastructure to prepare 10GB, 100GB, 500GB, 1TB, and 2TB datasets
2. **Run SageMaker training**: Use prepared datasets for cross-AZ validation (Task 3)
3. **Measure performance**: Collect metrics during training (Task 4)
4. **Generate reports**: Analyze results and generate validation reports (Task 5)

## Getting Help

- **Documentation**: See `EC2_DATA_PREP_README.md` for detailed information
- **Examples**: See `example_ec2_data_prep_workflow.py` for code examples
- **Tests**: See `tests/test_ec2_data_prep_manager.py` for usage patterns
- **Logs**: Check FSx logs at `/mnt/fsx/${DEST_SUBDIR}/logs/`

## Summary

You now have a fully automated EC2-based data preparation infrastructure that:

✅ Minimizes costs through same-AZ transfers  
✅ Automates the complete workflow  
✅ Provides comprehensive logging and monitoring  
✅ Handles errors gracefully  
✅ Scales from 10GB to 2TB  

Start with a small dataset (10GB) to verify everything works, then scale up to larger datasets as needed.
