#!/bin/bash
# Setup CloudWatch Logs Agent on EC2 Instance
# This script installs and configures CloudWatch Logs agent for real-time log streaming

set -e

LOG_GROUP_NAME="/aws/ec2/data-prep"
LOG_STREAM_NAME="$(hostname)-$(date +%Y%m%d-%H%M%S)"
REGION="${AWS_DEFAULT_REGION:-us-west-2}"

echo "Setting up CloudWatch Logs..."
echo "  Log Group: $LOG_GROUP_NAME"
echo "  Log Stream: $LOG_STREAM_NAME"
echo "  Region: $REGION"

# Install CloudWatch Logs agent
echo "Installing CloudWatch Logs agent..."
yum install -y amazon-cloudwatch-agent

# Create CloudWatch Logs configuration
cat > /opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json <<EOF
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/data-prep.log",
            "log_group_name": "$LOG_GROUP_NAME",
            "log_stream_name": "$LOG_STREAM_NAME",
            "timezone": "UTC"
          },
          {
            "file_path": "/data-prep/logs/download.log",
            "log_group_name": "$LOG_GROUP_NAME",
            "log_stream_name": "${LOG_STREAM_NAME}-download",
            "timezone": "UTC"
          },
          {
            "file_path": "/data-prep/logs/upload.log",
            "log_group_name": "$LOG_GROUP_NAME",
            "log_stream_name": "${LOG_STREAM_NAME}-upload",
            "timezone": "UTC"
          },
          {
            "file_path": "/data-prep/logs/validation.log",
            "log_group_name": "$LOG_GROUP_NAME",
            "log_stream_name": "${LOG_STREAM_NAME}-validation",
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

echo "✓ CloudWatch Logs agent configured and started"
echo ""
echo "View logs with:"
echo "  aws logs tail $LOG_GROUP_NAME --follow --region $REGION"
