# EC2 Data Preparation Infrastructure

This infrastructure automates the preparation of genomic datasets (hg38 chromosome data) by launching EC2 instances in the same AZ as the FSx volume, minimizing data transfer costs and time.

## Overview

For larger datasets (500GB+), data preparation should be performed on an EC2 instance in the same AZ as the FSx volume to:
- **Eliminate cross-AZ transfer charges**: Same-AZ transfers are free
- **Maximize transfer speed**: Same-AZ network performance is optimal
- **Reduce preparation time**: Faster downloads and uploads

### Cost Optimization

**Cross-AZ Transfer Costs (without EC2)**:
- Transfer rate: $0.01/GB
- 2TB dataset: ~$20 in transfer costs

**Same-AZ Transfer with EC2**:
- Transfer cost: $0 (same-AZ is free)
- EC2 cost: ~$0.68/hour (c5.4xlarge)
- Typical preparation time: 2-4 hours for 2TB = ~$2.72
- **Net savings: ~$17 for 2TB preparation**

## Components

### 1. EC2 Data Prep Manager (`ec2_data_prep_manager.py`)

Python module for managing EC2 instance lifecycle:

**Key Features**:
- Launch EC2 instances with proper configuration
- Wait for instance readiness
- Monitor instance status
- Retrieve console output for debugging
- Terminate instances and cleanup

**Configuration**:
- Instance Type: `c5.4xlarge` (16 vCPUs, 32GB RAM)
- Placement: Same AZ as FSx volume (us-west-2a)
- Storage: 500GB EBS volume (gp3, encrypted)
- Network: Enhanced networking enabled
- IAM Role: Automatic creation with FSx and CloudWatch permissions

**Usage**:

```python
from ec2_data_prep_manager import EC2DataPrepManager

# Initialize manager
manager = EC2DataPrepManager(
    region="us-west-2",
    availability_zone="us-west-2a",
    instance_type="c5.4xlarge",
    volume_size_gb=500
)

# Launch instance
instance_info = manager.launch_instance(
    subnet_id="subnet-xxxxx",
    security_group_id="sg-xxxxx",
    user_data_script=user_data,
    instance_name="data-prep-10gb"
)

# Wait for ready
manager.wait_for_ready(instance_info['instance_id'])

# Monitor status
status = manager.get_instance_status(instance_info['instance_id'])

# Terminate when done
manager.terminate_instance(instance_info['instance_id'])
```

**CLI Usage**:

```bash
# Launch instance
python ec2_data_prep_manager.py launch \
    --subnet-id subnet-xxxxx \
    --security-group-id sg-xxxxx \
    --user-data user_data_script.sh \
    --instance-name data-prep-10gb

# Check status
python ec2_data_prep_manager.py status \
    --instance-id i-xxxxx

# Get console output
python ec2_data_prep_manager.py console \
    --instance-id i-xxxxx

# Terminate instance
python ec2_data_prep_manager.py terminate \
    --instance-id i-xxxxx \
    --wait
```

### 2. User Data Script (`user_data_script.sh`)

Bash script that runs on EC2 instance launch to automate the complete data preparation workflow.

**Workflow**:
1. Update system and install dependencies (Python, NFS utils, boto3)
2. Mount FSx volume via NFS
3. Download hg38 chromosome data from UCSC
4. Calculate checksums for integrity verification
5. Upload data to FSx volume
6. Validate upload integrity
7. Copy logs to FSx
8. Cleanup local data
9. Unmount FSx
10. Auto-terminate instance (optional)

**Environment Variables**:
- `FSX_DNS_NAME`: FSx SVM DNS name (required)
- `FSX_MOUNT_NAME`: FSx volume junction path (default: /genomics)
- `CHROMOSOMES`: Space-separated list of chromosomes (default: chr1 chr2)
- `DEST_SUBDIR`: Destination subdirectory on FSx (default: phase_10gb)
- `VOLUME_SIZE`: Target dataset size (default: 10GB)
- `S3_SCRIPTS_BUCKET`: S3 bucket with data prep scripts (optional)
- `AUTO_TERMINATE`: Auto-terminate after completion (default: false)

**Logs**:
- Main log: `/var/log/data-prep.log`
- Download log: `/data-prep/logs/download.log`
- Checksum log: `/data-prep/logs/checksum.log`
- Upload log: `/data-prep/logs/upload.log`
- Validation log: `/data-prep/logs/validation.log`

All logs are copied to FSx at: `${FSX_MOUNT}/${DEST_SUBDIR}/logs/`

### 3. Dataset Preparation Orchestrator (`prepare_dataset_on_ec2.py`)

High-level orchestration script that provides a simple CLI interface for preparing datasets.

**Features**:
- Automatic FSx information retrieval
- Security group creation and configuration
- User data script generation with configuration
- EC2 instance launch and monitoring
- Progress tracking and timeout handling
- Automatic cleanup on errors
- Results reporting

**Usage**:

```bash
# Prepare 10GB dataset
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-xxxxx \
    --volume-size 10GB \
    --chromosomes chr1 chr2 \
    --dest-subdir phase_10gb

# Prepare 100GB dataset
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-xxxxx \
    --volume-size 100GB \
    --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 \
    --dest-subdir phase_100gb

# Prepare 500GB dataset with custom configuration
python prepare_dataset_on_ec2.py \
    --fsx-file-system-id fs-xxxxx \
    --fsx-mount-name /genomics \
    --volume-size 500GB \
    --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 chr11 chr12 chr13 chr14 chr15 chr16 chr17 chr18 chr19 chr20 chr21 chr22 chrX \
    --dest-subdir phase_500gb \
    --s3-scripts-bucket my-scripts-bucket \
    --no-auto-terminate \
    --monitor-interval 120 \
    --max-runtime-hours 6 \
    --output results.json
```

**Parameters**:
- `--fsx-file-system-id`: FSx file system ID (required)
- `--fsx-mount-name`: FSx volume junction path (default: /genomics)
- `--volume-size`: Target dataset size (10GB, 100GB, 500GB, 1TB, 2TB)
- `--chromosomes`: List of chromosomes to download (required)
- `--dest-subdir`: Destination subdirectory on FSx (required)
- `--s3-scripts-bucket`: S3 bucket with data prep scripts (optional)
- `--no-auto-terminate`: Keep instance running after completion
- `--region`: AWS region (default: us-west-2)
- `--availability-zone`: AZ for EC2 instance (default: us-west-2a)
- `--monitor-interval`: Monitoring interval in seconds (default: 60)
- `--max-runtime-hours`: Maximum runtime before timeout (default: 8)
- `--output`: Output file for results in JSON format

**Output**:

```json
{
  "success": true,
  "instance_id": "i-xxxxx",
  "duration_seconds": 3600,
  "duration_human": "60.0 minutes",
  "volume_size": "100GB",
  "dest_subdir": "phase_100gb",
  "chromosomes": ["chr1", "chr2", "chr3", "chr4", "chr5", "chr6", "chr7", "chr8", "chr9", "chr10"],
  "completion_time": "2024-01-15T10:30:45Z"
}
```

## Chromosome Selection by Dataset Size

### 10GB Dataset
```bash
--chromosomes chr1 chr2
```
- 2 chromosomes
- ~5GB each
- Total: ~10GB

### 100GB Dataset
```bash
--chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10
```
- 10 chromosomes
- ~10GB each
- Total: ~100GB

### 500GB Dataset
```bash
--chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 chr11 chr12 chr13 chr14 chr15 chr16 chr17 chr18 chr19 chr20 chr21 chr22 chrX
```
- 23 chromosomes (chr1-chr22 + chrX)
- Total: ~500GB

### 1TB Dataset
- All chromosomes with different preprocessing variants
- Requires custom script modifications

### 2TB Dataset
- All chromosomes with multiple preprocessing variants
- Requires custom script modifications

## Integration with Existing Data Preparation Scripts

The EC2 infrastructure integrates with existing data preparation modules:

1. **hg38_downloader.py**: Downloads chromosome data from UCSC
2. **checksum_calculator.py**: Calculates MD5 and SHA256 checksums
3. **fsx_uploader.py**: Uploads data to FSx with integrity verification
4. **data_integrity_validator.py**: Validates upload integrity

These scripts should be:
- Uploaded to S3 bucket (recommended)
- Embedded in user data script (for small scripts)
- Cloned from git repository (alternative)

## Security Considerations

### IAM Role Permissions
The EC2 instance is assigned an IAM role with:
- FSx read/describe permissions
- CloudWatch Logs write permissions
- S3 read permissions (if using S3 for scripts)

### Security Groups
- EC2 security group: Allows outbound traffic only
- FSx security group: Updated to allow NFS (port 2049) from EC2 security group
- No inbound SSH access by default (add key-name for debugging)

### Data Encryption
- EBS volume: Encrypted at rest
- FSx volume: Encrypted at rest (configured in FSx stack)
- NFS traffic: Unencrypted (consider NFS with Kerberos for production)

## Monitoring and Debugging

### CloudWatch Logs
EC2 instance sends logs to CloudWatch Logs (if CloudWatch agent is configured).

### Console Output
Retrieve console output for debugging:

```bash
python ec2_data_prep_manager.py console --instance-id i-xxxxx
```

### FSx Logs
All preparation logs are copied to FSx:

```
${FSX_MOUNT}/${DEST_SUBDIR}/logs/
├── data-prep.log          # Main log
├── download.log           # Download progress
├── checksum.log           # Checksum calculation
├── upload.log             # Upload progress
├── validation.log         # Validation results
└── validation_report.json # Detailed validation report
```

### Instance Status
Check instance status:

```bash
python ec2_data_prep_manager.py status --instance-id i-xxxxx
```

## Error Handling

### Mount Failures
- Retries: 5 attempts with 10-second delay
- Logs: Detailed error messages in console output
- Recovery: Manual intervention required

### Download Failures
- Retries: 3 attempts per file with 5-second delay
- Logs: Download errors in download.log
- Recovery: Script exits, instance remains for debugging

### Upload Failures
- Retries: 3 attempts per file with 5-second delay
- Logs: Upload errors in upload.log
- Recovery: Script exits, instance remains for debugging

### Validation Failures
- Checksum mismatches logged in validation.log
- Script exits with error code
- Instance remains for debugging

### Timeout
- Maximum runtime: 8 hours (configurable)
- Automatic instance termination on timeout
- Logs preserved on FSx

## Cost Estimation

### EC2 Instance Costs
- Instance type: c5.4xlarge
- On-demand rate: ~$0.68/hour
- Spot instance rate: ~$0.20/hour (70% savings)

### Data Transfer Costs
- Same-AZ (EC2 to FSx): $0/GB
- Cross-AZ (local to FSx): $0.01/GB

### Storage Costs
- EBS volume: ~$0.10/GB-month (gp3)
- 500GB volume: ~$50/month (deleted after use)

### Example: 2TB Dataset Preparation
- EC2 runtime: 4 hours
- EC2 cost: 4 × $0.68 = $2.72
- Data transfer: $0 (same-AZ)
- **Total: $2.72**

Compare to cross-AZ transfer: 2TB × $0.01/GB = $20.48

**Savings: $17.76 (87% reduction)**

## Best Practices

1. **Use Same AZ**: Always launch EC2 in same AZ as FSx
2. **Auto-terminate**: Enable auto-termination to minimize costs
3. **Monitor Progress**: Check logs regularly during long preparations
4. **Use Spot Instances**: Consider spot instances for 70% cost savings
5. **Cleanup**: Ensure instances are terminated after completion
6. **S3 Scripts**: Store data prep scripts in S3 for easy updates
7. **Test Small First**: Test with 10GB dataset before larger scales
8. **Set Timeouts**: Configure appropriate max runtime for dataset size

## Troubleshooting

### Instance Won't Start
- Check subnet and security group configuration
- Verify IAM role permissions
- Check EC2 service limits

### Mount Fails
- Verify FSx SVM DNS name
- Check security group rules (NFS port 2049)
- Ensure FSx volume is available

### Download Slow
- Check network connectivity
- Verify UCSC server availability
- Consider increasing instance size

### Upload Slow
- Check FSx throughput capacity
- Monitor FSx performance metrics
- Consider increasing FSx throughput

### Validation Fails
- Check checksum logs for mismatches
- Verify source data integrity
- Re-run preparation with fresh download

## Future Enhancements

1. **Parallel Downloads**: Download multiple chromosomes in parallel
2. **Spot Instances**: Add support for spot instances
3. **Progress Reporting**: Real-time progress updates via CloudWatch
4. **SNS Notifications**: Send notifications on completion/failure
5. **Multi-AZ Support**: Support for multiple FSx volumes
6. **Resume Capability**: Resume interrupted preparations
7. **Compression**: On-the-fly compression during upload
8. **Deduplication**: Detect and skip duplicate data
