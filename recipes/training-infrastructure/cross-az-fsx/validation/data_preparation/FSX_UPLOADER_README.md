# FSx Volume Data Uploader

## Overview

The FSx Uploader module uploads downloaded hg38 chromosome data to FSx NetApp ONTAP volumes with robust error handling, progress tracking, and integrity verification.

## Features

- **Progress Tracking**: Real-time upload progress with size and rate information
- **Error Handling**: Automatic retry logic with configurable attempts and delays
- **Integrity Verification**: MD5 checksum validation to ensure upload integrity
- **Resume Support**: Skip files that already exist with matching checksums
- **Manifest Generation**: JSON manifest with upload metadata and checksums
- **Mount Verification**: Validates FSx mount accessibility before upload

## Prerequisites

- FSx NetApp ONTAP volume deployed and mounted
- Downloaded hg38 chromosome data (see `hg38_downloader.py`)
- Python 3.7+
- Sufficient permissions to write to FSx mount point

## FSx Volume Setup

Before using the uploader, ensure your FSx volume is properly mounted:

### 1. Get SVM DNS Name

```bash
# Get SVM ID from CloudFormation stack
SVM_ID=$(aws cloudformation describe-stacks \
  --stack-name CrossAzFsxSageMakerFsx \
  --query 'Stacks[0].Outputs[?OutputKey==`StorageVirtualMachineId`].OutputValue' \
  --output text)

# Get SVM DNS name
SVM_DNS=$(aws fsx describe-storage-virtual-machines \
  --storage-virtual-machine-ids $SVM_ID \
  --query 'StorageVirtualMachines[0].Endpoints.Nfs.DNSName' \
  --output text)

echo "SVM DNS: $SVM_DNS"
```

### 2. Mount FSx Volume

```bash
# Create mount point
sudo mkdir -p /mnt/fsx

# Mount the FSx volume
sudo mount -t nfs ${SVM_DNS}:/genomics /mnt/fsx

# Verify mount
df -h /mnt/fsx
ls -la /mnt/fsx
```

### 3. Set Permissions (if needed)

```bash
# Ensure write permissions
sudo chmod 777 /mnt/fsx
```

## Usage

### Command-Line Interface

#### Basic Upload

Upload all `.fa.gz` files from source directory to FSx mount:

```bash
python fsx_uploader.py \
  --source-dir ./hg38_data \
  --fsx-mount /mnt/fsx
```

#### Upload to Subdirectory

Upload files to a specific subdirectory within the FSx mount:

```bash
python fsx_uploader.py \
  --source-dir ./validation_datasets/10gb \
  --fsx-mount /mnt/fsx \
  --dest-subdir phase_10gb
```

#### Custom File Pattern

Upload files matching a specific pattern:

```bash
python fsx_uploader.py \
  --source-dir ./hg38_data \
  --fsx-mount /mnt/fsx \
  --pattern "chr*.fa.gz"
```

#### Disable Checksum Verification

Skip checksum verification for faster uploads (not recommended):

```bash
python fsx_uploader.py \
  --source-dir ./hg38_data \
  --fsx-mount /mnt/fsx \
  --no-verify
```

#### Force Re-upload

Re-upload all files, even if they already exist:

```bash
python fsx_uploader.py \
  --source-dir ./hg38_data \
  --fsx-mount /mnt/fsx \
  --no-resume
```

#### Verify Uploaded Files

Verify integrity of previously uploaded files:

```bash
python fsx_uploader.py \
  --source-dir ./hg38_data \
  --fsx-mount /mnt/fsx \
  --verify-only
```

#### Custom Retry Configuration

Configure retry behavior:

```bash
python fsx_uploader.py \
  --source-dir ./hg38_data \
  --fsx-mount /mnt/fsx \
  --max-retries 5 \
  --retry-delay 10
```

### Python API

#### Basic Upload

```python
from fsx_uploader import FSxUploader

# Initialize uploader
uploader = FSxUploader(
    source_dir="./hg38_data",
    fsx_mount_point="/mnt/fsx",
    verify_checksums=True,
    resume=True
)

# Verify mount access
if not uploader.verify_mount_access():
    raise RuntimeError("FSx mount is not accessible")

# Upload all files
result = uploader.upload_directory(pattern="*.fa.gz")

# Save manifest
uploader.save_upload_manifest(result)

print(f"Uploaded {result['uploaded_files']} files")
print(f"Total size: {result['total_size_bytes']} bytes")
```

#### Upload Single File

```python
from pathlib import Path
from fsx_uploader import FSxUploader

uploader = FSxUploader(
    source_dir="./hg38_data",
    fsx_mount_point="/mnt/fsx"
)

# Upload single file
source_file = Path("./hg38_data/chr1.fa.gz")
result = uploader.upload_file(source_file, dest_subdir="chromosomes")

print(f"Status: {result['status']}")
print(f"Upload time: {result['upload_time_seconds']:.2f}s")
```

#### Verify Upload Integrity

```python
from fsx_uploader import FSxUploader

uploader = FSxUploader(
    source_dir="./hg38_data",
    fsx_mount_point="/mnt/fsx"
)

# Verify all uploaded files
results = uploader.verify_uploaded_files()

failed = [f for f, passed in results.items() if not passed]
if failed:
    print(f"Failed verification: {failed}")
else:
    print("All files verified successfully")
```

## Upload Manifest

The uploader generates a JSON manifest with upload metadata:

```json
{
  "uploaded_at": "2024-01-15T10:30:45Z",
  "source_dir": "/path/to/hg38_data",
  "fsx_mount_point": "/mnt/fsx",
  "summary": {
    "total_files": 25,
    "uploaded_files": 20,
    "skipped_files": 5,
    "failed_files": 0,
    "total_size_bytes": 107374182400,
    "total_size_human": "100.00 GB",
    "total_time_seconds": 1234.56
  },
  "files": [
    {
      "filename": "chr1.fa.gz",
      "source_path": "/path/to/hg38_data/chr1.fa.gz",
      "dest_path": "/mnt/fsx/chr1.fa.gz",
      "size_bytes": 5368709120,
      "upload_time_seconds": 123.45,
      "checksum_source": "abc123...",
      "checksum_dest": "abc123...",
      "status": "uploaded"
    }
  ]
}
```

## Error Handling

### Mount Not Accessible

If the FSx mount is not accessible:

```
ERROR - FSx mount point is not writable: /mnt/fsx
```

**Solution**: Verify mount status and permissions:

```bash
# Check if mounted
mount | grep /mnt/fsx

# Re-mount if needed
sudo mount -t nfs ${SVM_DNS}:/genomics /mnt/fsx

# Check permissions
ls -la /mnt/fsx
```

### Upload Failures

If uploads fail after retries:

```
ERROR - Failed to upload chr1.fa.gz after 3 attempts
```

**Solution**: Check network connectivity and FSx volume status:

```bash
# Test network connectivity
ping ${SVM_DNS}

# Check FSx volume status
aws fsx describe-file-systems --file-system-ids fs-04b3f909e86004fc2
```

### Checksum Mismatch

If checksum verification fails:

```
ERROR - Checksum mismatch after upload: source=abc123, dest=def456
```

**Solution**: This indicates data corruption during upload. The uploader will automatically retry. If it persists:
- Check network stability
- Check FSx volume health
- Consider disabling checksum verification temporarily (not recommended)

## Performance Considerations

### Upload Speed

Upload speed depends on:
- Network bandwidth between compute and FSx
- FSx throughput capacity (128 MBps default)
- File size (larger files = better throughput)
- Cross-AZ latency (1-2ms typical)

Expected upload rates:
- Same-AZ: 100-128 MB/s
- Cross-AZ: 80-100 MB/s

### Optimization Tips

1. **Increase FSx Throughput**: For faster uploads, increase FSx throughput capacity
2. **Parallel Uploads**: Run multiple uploader instances for different file sets
3. **Disable Verification**: Skip checksum verification for faster uploads (not recommended)
4. **Use Resume**: Enable resume to skip already-uploaded files

## Integration with Validation Workflow

### Phase 2.5: Upload 10GB Dataset

```bash
# Download data
python hg38_downloader.py \
  --output-dir ./validation_datasets/10gb \
  --chromosomes chr1 chr2

# Upload to FSx
python fsx_uploader.py \
  --source-dir ./validation_datasets/10gb \
  --fsx-mount /mnt/fsx \
  --dest-subdir phase_10gb
```

### Phase 2.6: Upload 100GB Dataset

```bash
# Download data
python hg38_downloader.py \
  --output-dir ./validation_datasets/100gb \
  --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10

# Upload to FSx
python fsx_uploader.py \
  --source-dir ./validation_datasets/100gb \
  --fsx-mount /mnt/fsx \
  --dest-subdir phase_100gb
```

### Automated Upload Script

```bash
#!/bin/bash
# upload_all_phases.sh

PHASES=("10gb" "100gb" "500gb" "1tb" "2tb")
FSX_MOUNT="/mnt/fsx"

for phase in "${PHASES[@]}"; do
  echo "Uploading ${phase} dataset..."
  
  python fsx_uploader.py \
    --source-dir "./validation_datasets/${phase}" \
    --fsx-mount "${FSX_MOUNT}" \
    --dest-subdir "phase_${phase}" \
    --max-retries 5
  
  if [ $? -ne 0 ]; then
    echo "Failed to upload ${phase} dataset"
    exit 1
  fi
done

echo "All phases uploaded successfully"
```

## Troubleshooting

### Issue: "FSx mount point does not exist"

**Cause**: Mount point directory not created or FSx not mounted

**Solution**:
```bash
sudo mkdir -p /mnt/fsx
sudo mount -t nfs ${SVM_DNS}:/genomics /mnt/fsx
```

### Issue: "Permission denied" when writing to FSx

**Cause**: Insufficient permissions on FSx volume

**Solution**:
```bash
# Check current permissions
ls -la /mnt/fsx

# Set permissions (if you have access)
sudo chmod 777 /mnt/fsx

# Or configure NFS export policy (see NFS_EXPORT_CONFIGURATION.md)
```

### Issue: Slow upload speeds

**Cause**: Network bandwidth limitations or FSx throughput limits

**Solution**:
- Check FSx throughput capacity setting
- Monitor network utilization
- Consider increasing FSx throughput capacity
- Verify cross-AZ network performance

### Issue: Upload interrupted and cannot resume

**Cause**: Partial file exists without matching checksum

**Solution**:
```bash
# Remove partial files from FSx
rm /mnt/fsx/partial_file.fa.gz

# Re-run upload with resume enabled (default)
python fsx_uploader.py --source-dir ./hg38_data --fsx-mount /mnt/fsx
```

## Testing

Run unit tests:

```bash
python -m pytest test_fsx_uploader.py -v
```

Run integration tests (requires mounted FSx volume):

```bash
python -m pytest test_fsx_uploader.py -v --integration
```

## Related Documentation

- [hg38_downloader.py](hg38_downloader.py) - Download chromosome data from UCSC
- [checksum_calculator.py](checksum_calculator.py) - Calculate and verify checksums
- [FSX_DEPLOYMENT_GUIDE.md](../../infrastructure/FSX_DEPLOYMENT_GUIDE.md) - FSx deployment instructions
- [NFS_EXPORT_CONFIGURATION.md](../../infrastructure/NFS_EXPORT_CONFIGURATION.md) - NFS export setup

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review FSx CloudWatch metrics for volume health
3. Verify network connectivity and security group rules
4. Check FSx volume status in AWS console
