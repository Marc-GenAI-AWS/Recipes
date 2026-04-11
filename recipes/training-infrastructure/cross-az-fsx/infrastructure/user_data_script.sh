#!/bin/bash
#
# EC2 User Data Script for Data Preparation
#
# This script runs on EC2 instance launch to:
# 1. Install dependencies (Python, NFS utils, boto3)
# 2. Mount FSx volume
# 3. Download hg38 chromosome data
# 4. Upload data to FSx
# 5. Validate data integrity
# 6. Signal completion and terminate instance
#
# Environment variables (passed via user data):
# - FSX_DNS_NAME: FSx SVM DNS name
# - FSX_MOUNT_NAME: FSx volume junction path (e.g., /genomics)
# - CHROMOSOMES: Space-separated list of chromosomes to download
# - DEST_SUBDIR: Destination subdirectory on FSx volume
# - VOLUME_SIZE: Target dataset size (e.g., 10GB, 100GB)
# - S3_SCRIPTS_BUCKET: S3 bucket containing data prep scripts (optional)
# - AUTO_TERMINATE: Set to "true" to auto-terminate after completion

set -e  # Exit on error
set -x  # Print commands for debugging

# Logging setup
LOG_FILE="/var/log/data-prep.log"
exec > >(tee -a ${LOG_FILE})
exec 2>&1

echo "=========================================="
echo "EC2 Data Preparation Script Started"
echo "Time: $(date)"
echo "=========================================="

# Default values
FSX_DNS_NAME="${FSX_DNS_NAME:-}"
FSX_MOUNT_NAME="${FSX_MOUNT_NAME:-/genomics}"
CHROMOSOMES="${CHROMOSOMES:-chr1 chr2}"
DEST_SUBDIR="${DEST_SUBDIR:-phase_10gb}"
VOLUME_SIZE="${VOLUME_SIZE:-10GB}"
S3_SCRIPTS_BUCKET="${S3_SCRIPTS_BUCKET:-}"
AUTO_TERMINATE="${AUTO_TERMINATE:-false}"

# Directories
WORK_DIR="/data-prep"
DOWNLOAD_DIR="${WORK_DIR}/hg38_data"
SCRIPTS_DIR="${WORK_DIR}/scripts"
FSX_MOUNT_POINT="/mnt/fsx"
LOGS_DIR="${WORK_DIR}/logs"

echo "Configuration:"
echo "  FSX_DNS_NAME: ${FSX_DNS_NAME}"
echo "  FSX_MOUNT_NAME: ${FSX_MOUNT_NAME}"
echo "  CHROMOSOMES: ${CHROMOSOMES}"
echo "  DEST_SUBDIR: ${DEST_SUBDIR}"
echo "  VOLUME_SIZE: ${VOLUME_SIZE}"
echo "  AUTO_TERMINATE: ${AUTO_TERMINATE}"

# Create working directories
mkdir -p ${WORK_DIR}
mkdir -p ${DOWNLOAD_DIR}
mkdir -p ${SCRIPTS_DIR}
mkdir -p ${FSX_MOUNT_POINT}
mkdir -p ${LOGS_DIR}

# Update system (skipped due to curl package conflicts in Amazon Linux 2023)
echo "Skipping system update to avoid package conflicts..."
# yum update -y --skip-broken || true

# Install dependencies
echo "Installing dependencies..."
yum install -y \
    python3 \
    python3-pip \
    nfs-utils \
    git \
    wget \
    curl

# Install Python packages
echo "Installing Python packages..."
pip3 install --upgrade pip
pip3 install boto3 requests

# Check if FSX_DNS_NAME is provided
if [ -z "${FSX_DNS_NAME}" ]; then
    echo "ERROR: FSX_DNS_NAME not provided"
    echo "Please set FSX_DNS_NAME environment variable"
    exit 1
fi

# Mount FSx volume
echo "Mounting FSx volume..."
echo "  DNS: ${FSX_DNS_NAME}"
echo "  Mount name: ${FSX_MOUNT_NAME}"
echo "  Mount point: ${FSX_MOUNT_POINT}"

# Try to mount with retries
MAX_MOUNT_RETRIES=5
MOUNT_RETRY_DELAY=10

for i in $(seq 1 ${MAX_MOUNT_RETRIES}); do
    echo "Mount attempt ${i}/${MAX_MOUNT_RETRIES}..."
    
    if mount -t nfs ${FSX_DNS_NAME}:${FSX_MOUNT_NAME} ${FSX_MOUNT_POINT}; then
        echo "✓ FSx volume mounted successfully"
        break
    else
        echo "✗ Mount attempt ${i} failed"
        
        if [ ${i} -eq ${MAX_MOUNT_RETRIES} ]; then
            echo "ERROR: Failed to mount FSx volume after ${MAX_MOUNT_RETRIES} attempts"
            exit 1
        fi
        
        echo "Retrying in ${MOUNT_RETRY_DELAY} seconds..."
        sleep ${MOUNT_RETRY_DELAY}
    fi
done

# Verify mount
if ! mountpoint -q ${FSX_MOUNT_POINT}; then
    echo "ERROR: FSx mount verification failed"
    exit 1
fi

echo "✓ FSx mount verified"

# Test write access
TEST_FILE="${FSX_MOUNT_POINT}/.write_test_$(date +%s)"
if echo "test" > ${TEST_FILE} 2>/dev/null; then
    rm -f ${TEST_FILE}
    echo "✓ FSx mount is writable"
else
    echo "ERROR: FSx mount is not writable"
    exit 1
fi

# Get data preparation scripts
echo "Setting up data preparation scripts..."

if [ -n "${S3_SCRIPTS_BUCKET}" ]; then
    # Download scripts from S3
    echo "Downloading scripts from S3: ${S3_SCRIPTS_BUCKET}"
    aws s3 sync s3://${S3_SCRIPTS_BUCKET}/ ${SCRIPTS_DIR}/
else
    # Clone from repository or copy embedded scripts
    echo "Using embedded scripts"
    
    # Create embedded versions of the scripts
    # In production, these would be downloaded from S3 or git repository
    cat > ${SCRIPTS_DIR}/hg38_downloader.py << 'SCRIPT_EOF'
# Placeholder: In production, copy actual hg38_downloader.py here
# or download from S3/git repository
import sys
print("ERROR: hg38_downloader.py not available")
print("Please provide S3_SCRIPTS_BUCKET or embed scripts")
sys.exit(1)
SCRIPT_EOF

    cat > ${SCRIPTS_DIR}/checksum_calculator.py << 'SCRIPT_EOF'
# Placeholder: In production, copy actual checksum_calculator.py here
import sys
print("ERROR: checksum_calculator.py not available")
sys.exit(1)
SCRIPT_EOF

    cat > ${SCRIPTS_DIR}/fsx_uploader.py << 'SCRIPT_EOF'
# Placeholder: In production, copy actual fsx_uploader.py here
import sys
print("ERROR: fsx_uploader.py not available")
sys.exit(1)
SCRIPT_EOF

    cat > ${SCRIPTS_DIR}/data_integrity_validator.py << 'SCRIPT_EOF'
# Placeholder: In production, copy actual data_integrity_validator.py here
import sys
print("ERROR: data_integrity_validator.py not available")
sys.exit(1)
SCRIPT_EOF
fi

# Make scripts executable
chmod +x ${SCRIPTS_DIR}/*.py

# Download hg38 chromosome data
echo "=========================================="
echo "Downloading hg38 chromosome data..."
echo "  Chromosomes: ${CHROMOSOMES}"
echo "  Destination: ${DOWNLOAD_DIR}"
echo "=========================================="

cd ${SCRIPTS_DIR}

python3 hg38_downloader.py \
    --output-dir ${DOWNLOAD_DIR} \
    --chromosomes ${CHROMOSOMES} \
    --max-retries 3 \
    --retry-delay 5 \
    2>&1 | tee ${LOGS_DIR}/download.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "ERROR: Download failed"
    exit 1
fi

echo "✓ Download completed"

# Calculate checksums
echo "=========================================="
echo "Calculating checksums..."
echo "=========================================="

python3 checksum_calculator.py \
    --data-dir ${DOWNLOAD_DIR} \
    --manifest ${DOWNLOAD_DIR}/checksums.json \
    2>&1 | tee ${LOGS_DIR}/checksum.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "ERROR: Checksum calculation failed"
    exit 1
fi

echo "✓ Checksums calculated"

# Upload to FSx
echo "=========================================="
echo "Uploading data to FSx..."
echo "  Source: ${DOWNLOAD_DIR}"
echo "  Destination: ${FSX_MOUNT_POINT}/${DEST_SUBDIR}"
echo "=========================================="

python3 fsx_uploader.py \
    --source-dir ${DOWNLOAD_DIR} \
    --fsx-mount ${FSX_MOUNT_POINT} \
    --dest-subdir ${DEST_SUBDIR} \
    --pattern "*.fa.gz" \
    --max-retries 3 \
    --retry-delay 5 \
    2>&1 | tee ${LOGS_DIR}/upload.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "ERROR: Upload failed"
    exit 1
fi

echo "✓ Upload completed"

# Validate data integrity
echo "=========================================="
echo "Validating data integrity..."
echo "=========================================="

python3 data_integrity_validator.py \
    --source-dir ${DOWNLOAD_DIR} \
    --fsx-mount ${FSX_MOUNT_POINT} \
    --dest-subdir ${DEST_SUBDIR} \
    --pattern "*.fa.gz" \
    --manifest ${DOWNLOAD_DIR}/checksums.json \
    --report ${LOGS_DIR}/validation_report.json \
    2>&1 | tee ${LOGS_DIR}/validation.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "ERROR: Validation failed"
    exit 1
fi

echo "✓ Validation completed"

# Copy logs to FSx
echo "Copying logs to FSx..."
LOG_DEST="${FSX_MOUNT_POINT}/${DEST_SUBDIR}/logs"
mkdir -p ${LOG_DEST}
cp -r ${LOGS_DIR}/* ${LOG_DEST}/
cp ${LOG_FILE} ${LOG_DEST}/
echo "✓ Logs copied to ${LOG_DEST}"

# Cleanup local data
echo "Cleaning up local data..."
rm -rf ${DOWNLOAD_DIR}
echo "✓ Cleanup completed"

# Unmount FSx
echo "Unmounting FSx volume..."
umount ${FSX_MOUNT_POINT}
echo "✓ FSx volume unmounted"

# Success
echo "=========================================="
echo "Data Preparation Completed Successfully"
echo "Time: $(date)"
echo "=========================================="

# Create completion marker
echo "SUCCESS" > ${WORK_DIR}/completion_status
echo "$(date)" >> ${WORK_DIR}/completion_status

# Auto-terminate if requested
if [ "${AUTO_TERMINATE}" = "true" ]; then
    echo "Auto-termination enabled, shutting down in 60 seconds..."
    echo "This allows time to retrieve logs if needed"
    sleep 60
    shutdown -h now
else
    echo "Auto-termination disabled, instance will remain running"
    echo "Terminate manually when ready"
fi
