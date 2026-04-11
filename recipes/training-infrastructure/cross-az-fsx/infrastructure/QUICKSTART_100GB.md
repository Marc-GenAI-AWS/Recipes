# Quick Start: 100GB Dataset Preparation with Real-Time Monitoring

This guide walks you through preparing the 100GB dataset (chr1-chr10) with CloudWatch Logs for real-time monitoring.

## Prerequisites

- ✅ 10GB dataset preparation completed successfully
- ✅ Scripts deployed to S3 bucket
- ✅ AWS credentials configured
- ✅ Python 3.8+ with boto3 installed

## Step 1: Launch the 100GB Job

Open PowerShell in the `infrastructure` directory and run:

```powershell
.\run_100gb_data_prep.ps1
```

The script will:
1. Verify prerequisites (S3 bucket, Python, boto3)
2. Display configuration and cost estimates
3. Ask for confirmation
4. Launch the EC2 instance with CloudWatch Logs enabled
5. **Automatically start streaming logs in real-time**

**Expected Output:**
```
========================================
100GB Dataset Preparation
========================================

Configuration:
  FSx File System: fs-04b3f909e86004fc2
  S3 Scripts Bucket: cross-az-fsx-sagemaker-scripts-xxxxx/scripts
  Region: us-west-2
  Availability Zone: us-west-2a
  Volume Size: 100GB
  Chromosomes: chr1-chr10
  Destination: phase_100gb
  CloudWatch Logs: ENABLED

This will:
  1. Launch a c5.4xlarge EC2 instance (~$0.68/hour)
  2. Download chr1-chr10 from UCSC (~100GB)
  3. Upload to FSx volume in us-west-2a
  4. Validate data integrity
  5. Stream logs to CloudWatch for real-time monitoring
  6. Terminate the instance automatically

Estimated time: 3-5 hours
Estimated cost: ~$2.04 - $3.40

Proceed? (yes/no):
```

Type `yes` and press Enter.

## Step 2: Watch Real-Time Progress

After you confirm, the script will automatically:
1. Launch the EC2 instance
2. Wait for CloudWatch Logs to become available (~60 seconds)
3. Start streaming logs directly to your terminal

**You don't need to open a second terminal!** Everything happens in one window.

The logs will stream in real-time, showing you exactly what's happening on the EC2 instance.

## What You'll See

The script will automatically stream logs after launching the instance. Here's what you'll see in your terminal:

### Phase 1: Instance Setup (5-10 minutes)
```
========================================
EC2 Data Preparation Script Started
Time: 2024-04-10 14:30:22
========================================

Configuration:
  Instance ID: i-0a1b2c3d4e5f6g7h8
  FSX_DNS_NAME: svm-04e40592311d0bdfb.fs-04b3f909e86004fc2.fsx.us-west-2.amazonaws.com
  CHROMOSOMES: chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10
  DEST_SUBDIR: phase_100gb
  VOLUME_SIZE: 100GB

Updating system packages...
Installing dependencies...
Installing Python packages...

========================================
Configuring CloudWatch Logs
========================================
✓ CloudWatch Logs agent started
  Log Group: /aws/ec2/data-prep
  Log Stream Prefix: i-0a1b2c3d4e5f6g7h8

========================================
Mounting FSx Volume
========================================
Mount attempt 1/5...
✓ FSx volume mounted successfully
✓ FSx mount is writable
```

### Phase 2: Download (2-3 hours)
```
========================================
Downloading hg38 Chromosome Data
  Chromosomes: chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10
  Destination: /data-prep/hg38_data
========================================

Downloading chr1.fa.gz...
  URL: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/chr1.fa.gz
  Size: 248.96 MB
  Progress: [=========>] 85%

Downloading chr2.fa.gz...
  URL: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/chr2.fa.gz
  Size: 242.19 MB
  Progress: [======>   ] 55%

...

✓ Download completed
  Total files: 10
  Total size: 1.2 GB
```

### Phase 3: Checksum Calculation (5-10 minutes)
```
========================================
Calculating Checksums
========================================

Calculating checksums for chr1.fa.gz...
  MD5: abc123def456...
  SHA256: xyz789uvw012...

Calculating checksums for chr2.fa.gz...
  MD5: 123abc456def...
  SHA256: 789xyz012uvw...

...

✓ Checksums calculated
  Manifest saved to: /data-prep/hg38_data/checksums.json
```

### Phase 4: Upload to FSx (30-60 minutes)
```
========================================
Uploading Data to FSx
  Source: /data-prep/hg38_data
  Destination: /mnt/fsx/phase_100gb
========================================

Uploading chr1.fa.gz... [=========>] 90%
Uploading chr2.fa.gz... [=======>  ] 70%

...

✓ Upload completed
  Total files: 10
  Total size: 1.2 GB
  Duration: 45.3 minutes
```

### Phase 5: Validation (10-15 minutes)
```
========================================
Validating Data Integrity
========================================

Validating file 1/10: chr1.fa.gz
  ✓ Size match: 248956422 bytes
  ✓ MD5 match: abc123def456...
  ✓ SHA256 match: xyz789uvw012...

Validating file 2/10: chr2.fa.gz
  ✓ Size match: 242193529 bytes
  ✓ MD5 match: 123abc456def...
  ✓ SHA256 match: 789xyz012uvw...

...

Validation complete:
  - Total files: 10
  - Valid: 10
  - Invalid: 0
  - Total size: 1.2 GB

✓ All files validated successfully
```

### Phase 6: Completion
```
Copying logs to FSx...
✓ Logs copied to /mnt/fsx/phase_100gb/logs

Cleaning up local data...
✓ Cleanup completed

Unmounting FSx volume...
✓ FSx volume unmounted

========================================
Data Preparation Completed Successfully
Time: 2024-04-10 18:45:33
========================================

Auto-termination enabled, shutting down in 60 seconds...
```

## Multiple Log Streams

CloudWatch Logs creates separate streams for different phases. By default, the script shows all logs combined, but you can view specific streams if needed.

**To view a specific stream in a separate terminal:**

```powershell
# Download progress only
aws logs tail /aws/ec2/data-prep --follow --region us-west-2 --log-stream-name-prefix i-xxxxx-download

# Upload progress only
aws logs tail /aws/ec2/data-prep --follow --region us-west-2 --log-stream-name-prefix i-xxxxx-upload

# Validation results only
aws logs tail /aws/ec2/data-prep --follow --region us-west-2 --log-stream-name-prefix i-xxxxx-validation
```

Replace `i-xxxxx` with your actual instance ID (shown in the logs).

## Stopping Log Streaming

If you want to stop watching the logs but let the job continue:

1. Press `Ctrl+C` to stop the log stream
2. The script will ask if you want to wait for job completion
3. Choose "no" to exit - the job will continue running in the background
4. Results will be saved to `results_100gb_*.json` when complete

**To check on the job later:**
```powershell
# View recent logs
aws logs tail /aws/ec2/data-prep --region us-west-2 --since 1h

# Check if results file exists
ls results_100gb_*.json
```

## Troubleshooting

### "Log group not found"

The log group is created when the CloudWatch agent first writes logs. Wait 2-3 minutes after instance launch and try again.

### Logs stop updating

Check instance state:
```powershell
aws ec2 describe-instances --instance-ids i-xxxxx --region us-west-2 --query 'Reservations[0].Instances[0].State.Name'
```

If the instance is `terminated` or `stopped`, check the results file:
```powershell
Get-Content results_100gb_*.json | ConvertFrom-Json | Format-List
```

### Job fails during download

The script has automatic retry logic (3 attempts with 5-second delays). If all retries fail, check:
1. Network connectivity from EC2 to UCSC servers
2. UCSC server availability
3. CloudWatch logs for detailed error messages

### Job fails during upload

Check:
1. FSx mount is accessible: `mountpoint -q /mnt/fsx`
2. FSx has sufficient space
3. Security group allows NFS traffic (port 2049)
4. CloudWatch logs for detailed error messages

## Cost Breakdown

**Compute (c5.4xlarge):**
- Hourly rate: $0.68
- Expected duration: 3-5 hours
- Cost: $2.04 - $3.40

**Data Transfer:**
- Same-AZ transfer (EC2 → FSx): FREE
- Internet download (UCSC → EC2): FREE

**CloudWatch Logs:**
- Log ingestion: ~50 MB × $0.50/GB = $0.025
- Log storage: ~50 MB × $0.03/GB/month = $0.0015/month

**Total: ~$2.07 - $3.43**

## Next Steps

After the 100GB job completes:

1. **Verify the data:**
   ```bash
   # Mount FSx locally or SSH to an EC2 instance
   ls -lh /mnt/fsx/phase_100gb/
   ```

2. **Review validation logs:**
   ```bash
   cat /mnt/fsx/phase_100gb/logs/validation_report.json
   ```

3. **Check CloudWatch Logs:**
   ```powershell
   aws logs tail /aws/ec2/data-prep --region us-west-2 --since 3h
   ```

4. **Proceed to 500GB dataset:**
   - Update `run_500gb_data_prep.ps1` (similar pattern)
   - Use chr1-chr22 + chrX
   - Estimated time: 10-15 hours
   - Estimated cost: ~$6.80 - $10.20

## Summary

The 100GB dataset preparation with CloudWatch Logs provides:
- ✅ Real-time visibility into job progress
- ✅ Separate log streams for each phase
- ✅ Searchable and filterable logs
- ✅ Historical log retention
- ✅ Automatic instance termination on completion
- ✅ Comprehensive validation and integrity checks

You can now monitor your data preparation jobs in real-time and have full visibility into every step of the process!
