#!/bin/bash
#
# EC2 User Data Script for Data Preparation with CloudWatch Logs
#
# This version streams logs to CloudWatch in real-time for monitoring

set -e  # Exit on error
set -x  # Print commands for debugging

# Logging setup - dual output to file and CloudWatch
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
S3_SCRIPTS_BUCKET="${S3_SCRIPTS_BUCKET:-}"
AUTO_TERMINATE="${AUTO_TERMINATE:-false}"
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# Directories
WORK_DIR="/data-prep"
DOWNLOAD_DIR="${WORK_DIR}/hg38_data"
SCRIPTS_DIR="${WORK_DIR}/scripts"
FSX_MOUNT_POINT="/mnt/fsx"
LOGS_DIR="${WORK_DIR}/logs"

echo "Configuration:"
echo "  Instance ID: ${INSTANCE_ID}"
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
    curl \
    amazon-cloudwatch-agent

# Install Python packages
echo "Installing Python packages..."
pip3 install --upgrade pip
pip3 install boto3 requests

# Configure CloudWatch Logs Agent
echo "=========================================="
echo "Configuring CloudWatch Logs"
echo "=========================================="

LOG_GROUP_NAME="/aws/ec2/data-prep"
LOG_STREAM_PREFIX="${INSTANCE_ID}"

cat > /opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json <<EOF
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/data-prep.log",
            "log_group_name": "${LOG_GROUP_NAME}",
            "log_stream_name": "${LOG_STREAM_PREFIX}-main",
            "timezone": "UTC",
            "timestamp_format": "%Y-%m-%d %H:%M:%S"
          },
          {
            "file_path": "/data-prep/logs/download.log",
            "log_group_name": "${LOG_GROUP_NAME}",
            "log_stream_name": "${LOG_STREAM_PREFIX}-download",
            "timezone": "UTC"
          },
          {
            "file_path": "/data-prep/logs/upload.log",
            "log_group_name": "${LOG_GROUP_NAME}",
            "log_stream_name": "${LOG_STREAM_PREFIX}-upload",
            "timezone": "UTC"
          },
          {
            "file_path": "/data-prep/logs/validation.log",
            "log_group_name": "${LOG_GROUP_NAME}",
            "log_stream_name": "${LOG_STREAM_PREFIX}-validation",
            "timezone": "UTC"
          }
        ]
      }
    }
  }
}
EOF

# Start CloudWatch Logs agent
echo "Starting CloudWatch Logs agent..."
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json

echo "✓ CloudWatch Logs agent started"
echo "  Log Group: ${LOG_GROUP_NAME}"
echo "  Log Stream Prefix: ${LOG_STREAM_PREFIX}"
echo ""
echo "View logs with:"
echo "  aws logs tail ${LOG_GROUP_NAME} --follow --region ${REGION}"
echo ""

# Check if FSX_DNS_NAME is provided
if [ -z "${FSX_DNS_NAME}" ]; then
    echo "ERROR: FSX_DNS_NAME not provided"
    exit 1
fi

# Mount FSx volume
echo "=========================================="
echo "Mounting FSx Volume"
echo "=========================================="
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

# Download data preparation scripts from S3
echo "=========================================="
echo "Downloading Data Preparation Scripts"
echo "=========================================="

if [ -n "${S3_SCRIPTS_BUCKET}" ]; then
    echo "Downloading scripts from S3: ${S3_SCRIPTS_BUCKET}"
    aws s3 sync "s3://${S3_SCRIPTS_BUCKET}/" ${SCRIPTS_DIR}/ --region ${REGION}
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to download scripts from S3"
        exit 1
    fi
    
    echo "✓ Scripts downloaded successfully"
else
    echo "ERROR: S3_SCRIPTS_BUCKET not provided"
    exit 1
fi

# Make scripts executable
chmod +x ${SCRIPTS_DIR}/*.py

# Download hg38 chromosome data
echo "=========================================="
echo "Downloading hg38 Chromosome Data"
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
echo "Calculating Checksums"
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
echo "Uploading Data to FSx"
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
echo "Validating Data Integrity"
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

# Flush CloudWatch logs
echo "Flushing CloudWatch logs..."
sleep 10

# Auto-terminate if requested
if [ "${AUTO_TERMINATE}" = "true" ]; then
    echo "Auto-termination enabled, shutting down in 60 seconds..."
    echo "This allows time to retrieve final logs"
    sleep 60
    shutdown -h now
else
    echo "Auto-termination disabled, instance will remain running"
    echo "Terminate manually when ready"
fi
