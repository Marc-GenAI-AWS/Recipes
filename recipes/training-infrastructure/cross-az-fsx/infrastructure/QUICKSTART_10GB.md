# Quick Start: 10GB Dataset Preparation

This guide will walk you through preparing your first 10GB dataset using EC2.

## Prerequisites

- AWS CLI configured with credentials
- Python 3.8+ installed
- boto3 installed (`pip install boto3`)
- FSx file system deployed (fs-04b3f909e86004fc2)

## Step 1: Deploy Scripts to S3

First, upload the data preparation scripts to S3:

```powershell
cd infrastructure
.\deploy_scripts_to_s3.ps1
```

This will:
- Create an S3 bucket (e.g., `fsx-validation-scripts-20240410`)
- Upload all data preparation scripts
- Save bucket information to `s3_bucket_info.txt`

**Expected output:**
```
========================================
Deploying Data Preparation Scripts to S3
========================================

Creating S3 bucket: fsx-validation-scripts-20240410
✓ Bucket created successfully

Uploading data preparation scripts...
✓ Scripts uploaded successfully

Uploaded files:
scripts/checksum_calculator.py
scripts/data_integrity_validator.py
scripts/fsx_uploader.py
scripts/hg38_downloader.py

========================================
Deployment Complete
========================================

S3 Bucket: fsx-validation-scripts-20240410
Scripts Path: s3://fsx-validation-scripts-20240410/scripts/
```

## Step 2: Run 10GB Data Preparation

Now run the automated data preparation:

```powershell
.\run_10gb_data_prep.ps1
```

This will:
1. Read S3 bucket info from `s3_bucket_info.txt`
2. Show configuration and cost estimate
3. Ask for confirmation
4. Launch EC2 instance
5. Monitor progress
6. Save results to JSON file

**Expected output:**
```
========================================
10GB Dataset Preparation
========================================

Configuration:
  FSx File System: fs-04b3f909e86004fc2
  S3 Scripts Bucket: fsx-validation-scripts-20240410/scripts
  Region: us-west-2
  Availability Zone: us-west-2a
  Volume Size: 10GB
  Chromosomes: chr1, chr2
  Destination: phase_10gb

This will:
  1. Launch a c5.4xlarge EC2 instance (~$0.68/hour)
  2. Download chr1 and chr2 from UCSC (~10GB)
  3. Upload to FSx volume in us-west-2a
  4. Validate data integrity
  5. Terminate the instance automatically

Estimated time: 30-60 minutes
Estimated cost: ~$0.34 - $0.68

Proceed? (yes/no): yes

========================================
Starting Data Preparation
========================================

Initialized DatasetPreparationOrchestrator
  Region: us-west-2
  AZ: us-west-2a

Getting FSx information for fs-04b3f909e86004fc2
FSx SVM DNS: svm-04e40592311d0bdfb.fs-04b3f909e86004fc2.fsx.us-west-2.amazonaws.com
Using subnet: subnet-xxxxx

Launching EC2 instance for data preparation
Instance launched: i-xxxxx
  Instance type: c5.4xlarge
  AZ: us-west-2a

Waiting for instance to be ready...
Instance is ready, data preparation in progress...

Monitoring progress (interval: 60s)
Maximum runtime: 2 hours

Instance state: running (elapsed: 1.0 min)
Instance state: running (elapsed: 2.0 min)
...
Instance state: terminated (elapsed: 45.3 min)
✓ Data preparation completed successfully

========================================
Dataset Preparation Complete
  Volume size: 10GB
  Destination: phase_10gb
  Duration: 45.3 minutes
========================================

========================================
Data Preparation Complete!
========================================

Results saved to: results_10gb_20240410_143022.json
```

## Step 3: Verify Results

Check the results file:

```powershell
Get-Content results_10gb_20240410_143022.json | ConvertFrom-Json | Format-List
```

**Expected output:**
```
success           : True
instance_id       : i-xxxxx
duration_seconds  : 2718
duration_human    : 45.3 minutes
volume_size       : 10GB
dest_subdir       : phase_10gb
chromosomes       : {chr1, chr2}
completion_time   : 2024-04-10T14:30:22Z
```

## Step 4: Verify Data on FSx

To verify the data was uploaded correctly, you can:

### Option A: Check from AWS Console
1. Go to FSx console
2. Navigate to your file system
3. Check the volume usage

### Option B: Mount FSx locally and check
```powershell
# Get SVM DNS name
aws fsx describe-storage-virtual-machines --region us-west-2

# Mount FSx (requires WSL or Linux)
sudo mount -t nfs <SVM-DNS>:/genomics /mnt/fsx

# Check uploaded files
ls -lh /mnt/fsx/phase_10gb/
cat /mnt/fsx/phase_10gb/logs/validation_report.json
```

### Option C: Launch another EC2 instance to verify
```powershell
# Launch a small instance in same AZ
aws ec2 run-instances `
    --image-id ami-xxxxx `
    --instance-type t3.micro `
    --subnet-id subnet-xxxxx `
    --security-group-ids sg-xxxxx

# SSH in and mount FSx
ssh ec2-user@<instance-ip>
sudo mount -t nfs <SVM-DNS>:/genomics /mnt/fsx
ls -lh /mnt/fsx/phase_10gb/
```

## Troubleshooting

### Script fails with "S3 bucket not specified"
**Solution**: Run `deploy_scripts_to_s3.ps1` first

### Instance launch fails
**Solution**: Check AWS service limits for EC2 instances in us-west-2

### Mount fails on EC2
**Solution**: 
1. Verify FSx security group allows NFS (port 2049) from EC2 security group
2. Check FSx SVM DNS name is correct
3. View console output: `aws ec2 get-console-output --instance-id i-xxxxx`

### Download is slow
**Solution**: This is normal for large chromosomes. chr1 is ~250MB compressed.

### Validation fails
**Solution**: Check validation logs on FSx at `/mnt/fsx/phase_10gb/logs/validation.log`

## Cost Breakdown

For 10GB dataset preparation:
- EC2 instance (c5.4xlarge): ~$0.34 - $0.68 (0.5-1 hour)
- Data transfer (same-AZ): $0
- EBS storage: $0 (deleted after use)
- **Total: ~$0.34 - $0.68**

## Next Steps

After successful 10GB preparation:
1. Review validation logs
2. Verify data integrity
3. Proceed with 100GB dataset: `.\run_100gb_data_prep.ps1`
4. Continue with larger datasets as needed

## Manual Execution (Alternative)

If you prefer to run manually without the wrapper script:

```powershell
python prepare_dataset_on_ec2.py `
    --fsx-file-system-id fs-04b3f909e86004fc2 `
    --volume-size 10GB `
    --chromosomes chr1 chr2 `
    --dest-subdir phase_10gb `
    --s3-scripts-bucket fsx-validation-scripts-20240410/scripts `
    --output results_10gb.json
```

## Getting Help

- Check logs on FSx: `/mnt/fsx/phase_10gb/logs/`
- View EC2 console output: `aws ec2 get-console-output --instance-id i-xxxxx`
- Review CloudWatch logs (if configured)
- See full documentation: `EC2_DATA_PREP_README.md`
