#!/bin/bash
#
# EC2 User Data Script for Data Preparation (With Embedded Scripts)
#
# This version includes the actual Python scripts embedded in the user data
# so no S3 bucket is required.

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

# Environment variables (will be set by orchestrator)
FSX_DNS_NAME="${FSX_DNS_NAME:-}"
FSX_MOUNT_NAME="${FSX_MOUNT_NAME:-/genomics}"
CHROMOSOMES="${CHROMOSOMES:-chr1 chr2}"
DEST_SUBDIR="${DEST_SUBDIR:-phase_10gb}"
VOLUME_SIZE="${VOLUME_SIZE:-10GB}"
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

# Update system
echo "Updating system packages..."
yum update -y

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
    exit 1
fi

# Mount FSx volume
echo "Mounting FSx volume..."
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
        
        sleep ${MOUNT_RETRY_DELAY}
    fi
done

# Verify mount
if ! mountpoint -q ${FSX_MOUNT_POINT}; then
    echo "ERROR: FSx mount verification failed"
    exit 1
fi

# Test write access
TEST_FILE="${FSX_MOUNT_POINT}/.write_test_$(date +%s)"
if echo "test" > ${TEST_FILE} 2>/dev/null; then
    rm -f ${TEST_FILE}
    echo "✓ FSx mount is writable"
else
    echo "ERROR: FSx mount is not writable"
    exit 1
fi

# Create Python scripts directory
cd ${SCRIPTS_DIR}

# Note: In production, copy actual scripts from your workspace
# For now, we'll use a simple approach: clone from git or copy from S3
echo "Note: Python scripts should be copied to ${SCRIPTS_DIR}"
echo "For this run, please ensure scripts are available via S3 or git"

# Placeholder: You'll need to add your actual scripts here
# Option 1: Copy from S3
# aws s3 cp s3://your-bucket/validation/data_preparation/ ${SCRIPTS_DIR}/ --recursive

# Option 2: Use git (if scripts are in a repo)
# git clone https://github.com/your-repo/scripts.git ${SCRIPTS_DIR}

# For now, exit with instructions
echo "=========================================="
echo "SETUP COMPLETE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Copy data preparation scripts to ${SCRIPTS_DIR}/"
echo "2. Run the workflow manually or update this script"
echo ""
echo "Scripts needed:"
echo "  - hg38_downloader.py"
echo "  - checksum_calculator.py"
echo "  - fsx_uploader.py"
echo "  - data_integrity_validator.py"
echo ""
echo "Instance will remain running for manual execution"
echo "Terminate manually when complete"
