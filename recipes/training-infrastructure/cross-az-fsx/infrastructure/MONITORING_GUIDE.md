# Real-Time Monitoring Guide

This guide shows you how to monitor your data preparation jobs in real-time.

## Quick Start: Monitor Your Running Job

### Option 1: Console Output (Simplest - Available Now)

While your job is running, open a new PowerShell terminal and run:

```powershell
# Replace i-xxxxx with your instance ID from the job output
.\monitor_data_prep.ps1 -InstanceId i-xxxxx
```

This will show:
- Instance state and elapsed time
- Real-time console output with color-coded messages
- Automatic highlighting of errors, successes, and progress

**Example output:**
```
========================================
Monitoring Data Preparation Progress
========================================

Instance ID: i-0a1b2c3d4e5f6g7h8
Refresh Interval: 30 seconds

[14:30:22] Instance State: running | Elapsed: 00:05:32

Updating system packages...
Installing dependencies...
✓ FSx volume mounted successfully
Downloading chromosome data from UCSC...
  Downloading chr1.fa.gz... 45% complete
```

### Option 2: CloudWatch Logs (Best for Production)

**Setup (one-time):**

The CloudWatch Logs agent needs to be added to the user data script. I'll show you how to enable this for future runs.

**For your current running job:**

You can still view console output with:

```powershell
# Watch console output continuously
aws ec2 get-console-output --instance-id i-xxxxx --region us-west-2 --output text

# Or use the monitoring script
.\monitor_data_prep.ps1 -InstanceId i-xxxxx
```

## Detailed Monitoring Options

### 1. EC2 Console Output (Available Now)

**Advantages:**
- ✅ Works immediately, no setup required
- ✅ Shows all output from the instance
- ✅ Good for debugging

**Disadvantages:**
- ❌ Limited to 64KB of output
- ❌ Can't filter or search easily
- ❌ Refreshes entire output each time

**Usage:**

```powershell
# One-time view
aws ec2 get-console-output --instance-id i-xxxxx --region us-west-2 --output text

# Continuous monitoring with our script
.\monitor_data_prep.ps1 -InstanceId i-xxxxx

# Manual continuous monitoring
while ($true) {
    Clear-Host
    Write-Host "=== Data Prep Progress ===" -ForegroundColor Cyan
    aws ec2 get-console-output --instance-id i-xxxxx --region us-west-2 --output text | Select-Object -Last 50
    Start-Sleep -Seconds 30
}
```

### 2. CloudWatch Logs (For Future Runs)

**Advantages:**
- ✅ Unlimited log retention
- ✅ Real-time streaming
- ✅ Searchable and filterable
- ✅ Can set up alarms
- ✅ Multiple log streams (download, upload, validation)

**Disadvantages:**
- ❌ Requires setup in user data script
- ❌ Small additional cost (~$0.50/GB ingested)

**Setup for Next Run:**

Update your `user_data_script.sh` to include CloudWatch Logs:

```bash
# Add this near the top of user_data_script.sh
# Install CloudWatch Logs agent
yum install -y amazon-cloudwatch-agent

# Configure CloudWatch Logs
cat > /opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json <<'EOF'
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/data-prep.log",
            "log_group_name": "/aws/ec2/data-prep",
            "log_stream_name": "{instance_id}-main",
            "timezone": "UTC"
          }
        ]
      }
    }
  }
}
EOF

# Start agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json
```

**Then watch logs:**

```powershell
# Watch all logs in real-time
aws logs tail /aws/ec2/data-prep --follow --region us-west-2

# Or use our script
.\watch_cloudwatch_logs.ps1
```

### 3. S3 Progress Files (Custom Solution)

For even more detailed progress tracking, you could have the scripts write progress to S3:

**Advantages:**
- ✅ Structured progress data (JSON)
- ✅ Can show percentage complete
- ✅ Easy to parse and display

**Implementation:**

Add to your Python scripts:

```python
import boto3
import json
from datetime import datetime

def update_progress(stage, percent, message):
    """Write progress to S3"""
    s3 = boto3.client('s3')
    progress = {
        'timestamp': datetime.utcnow().isoformat(),
        'stage': stage,
        'percent': percent,
        'message': message
    }
    s3.put_object(
        Bucket='your-bucket',
        Key=f'progress/{instance_id}.json',
        Body=json.dumps(progress)
    )

# Usage in scripts:
update_progress('download', 25, 'Downloading chr1.fa.gz')
update_progress('download', 50, 'Downloading chr2.fa.gz')
update_progress('upload', 75, 'Uploading to FSx')
update_progress('validation', 90, 'Validating checksums')
update_progress('complete', 100, 'All done!')
```

**Monitor progress:**

```powershell
# Watch progress file
while ($true) {
    $progress = aws s3 cp s3://your-bucket/progress/i-xxxxx.json - | ConvertFrom-Json
    Write-Host "[$($progress.timestamp)] $($progress.stage): $($progress.percent)% - $($progress.message)"
    Start-Sleep -Seconds 10
}
```

## Recommended Approach

**For your current job (running now):**
```powershell
.\monitor_data_prep.ps1 -InstanceId i-xxxxx
```

**For future jobs:**
1. Add CloudWatch Logs to user data script (one-time setup)
2. Use `aws logs tail` for real-time monitoring
3. Keep console output as backup

## What You'll See

### Download Phase (~20-30 minutes)
```
Downloading hg38 chromosome data...
  Chromosomes: chr1 chr2
  Destination: /data-prep/hg38_data

Downloading chr1.fa.gz...
  URL: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/chr1.fa.gz
  Size: ~250 MB
  Progress: [=====>    ] 45%

Downloading chr2.fa.gz...
  URL: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/chr2.fa.gz
  Size: ~240 MB
  Progress: [====>     ] 35%

✓ Successfully downloaded 2 chromosomes
```

### Checksum Phase (~5 minutes)
```
Calculating checksums for downloaded files...
  chr1.fa.gz: MD5=abc123..., SHA256=def456...
  chr2.fa.gz: MD5=xyz789..., SHA256=uvw012...

✓ Checksums calculated and saved
```

### Upload Phase (~10-15 minutes)
```
Uploading data to FSx volume...
  Source: /data-prep/hg38_data
  Destination: /mnt/fsx/phase_10gb

Uploading chr1.fa.gz... [=======>  ] 65%
Uploading chr2.fa.gz... [====>     ] 40%

✓ Upload complete
```

### Validation Phase (~5 minutes)
```
Validating upload integrity...
  Validating file 1/2: chr1.fa.gz
    ✓ Size match: 248956422 bytes
    ✓ MD5 match: abc123...
    ✓ SHA256 match: def456...

  Validating file 2/2: chr2.fa.gz
    ✓ Size match: 242193529 bytes
    ✓ MD5 match: xyz789...
    ✓ SHA256 match: uvw012...

Validation complete:
  - Total files: 2
  - Valid: 2
  - Invalid: 0
  - Total size: 467.5 MB

✓ All files validated successfully
```

### Completion
```
========================================
Data Preparation Completed Successfully
========================================

Duration: 45.3 minutes
Logs copied to: /mnt/fsx/phase_10gb/logs/

Auto-termination enabled, shutting down in 60 seconds...
```

## Troubleshooting

### "Instance not found"
The instance may have already terminated. Check the results JSON file.

### "No console output available"
Wait a few minutes after launch. Console output takes time to appear.

### "CloudWatch log group not found"
The log group is created when the agent first writes logs. Wait 2-3 minutes after instance launch.

### Logs stop updating
Check instance state:
```powershell
aws ec2 describe-instances --instance-ids i-xxxxx --region us-west-2 --query 'Reservations[0].Instances[0].State.Name'
```

## Cost of Monitoring

- **Console Output**: Free
- **CloudWatch Logs**: ~$0.50/GB ingested + $0.03/GB stored
- **S3 Progress Files**: Negligible (~$0.001)

For a 10GB job with verbose logging:
- Log data: ~10-50 MB
- CloudWatch cost: ~$0.01
- **Total monitoring cost: < $0.02**

## Summary

**Right now (for your running job):**
```powershell
.\monitor_data_prep.ps1 -InstanceId i-xxxxx
```

**For next time (better monitoring):**
1. Enable CloudWatch Logs in user data
2. Use `aws logs tail` for real-time streaming
3. Set up CloudWatch alarms for failures

The monitoring script I created gives you real-time visibility into your job with color-coded output and automatic error highlighting!
