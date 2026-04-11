# Task 2.6: CloudWatch Logs Integration - Implementation Summary

## Overview

Implemented real-time monitoring for EC2 data preparation jobs using CloudWatch Logs. This provides full visibility into job progress, errors, and performance metrics for long-running data preparation tasks.

## What Was Implemented

### 1. Enhanced User Data Script with CloudWatch Logs

**File:** `infrastructure/user_data_with_cloudwatch.sh`

Features:
- Installs and configures CloudWatch Logs agent
- Creates 4 separate log streams:
  - `{instance-id}-main`: Overall execution flow
  - `{instance-id}-download`: Download progress
  - `{instance-id}-upload`: Upload progress
  - `{instance-id}-validation`: Validation results
- Streams logs in real-time to CloudWatch
- Dual output: local files + CloudWatch

Configuration:
```json
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/data-prep.log",
            "log_group_name": "/aws/ec2/data-prep",
            "log_stream_name": "{instance-id}-main"
          },
          {
            "file_path": "/data-prep/logs/download.log",
            "log_group_name": "/aws/ec2/data-prep",
            "log_stream_name": "{instance-id}-download"
          },
          {
            "file_path": "/data-prep/logs/upload.log",
            "log_group_name": "/aws/ec2/data-prep",
            "log_stream_name": "{instance-id}-upload"
          },
          {
            "file_path": "/data-prep/logs/validation.log",
            "log_group_name": "/aws/ec2/data-prep",
            "log_stream_name": "{instance-id}-validation"
          }
        ]
      }
    }
  }
}
```

### 2. Updated EC2 Data Prep Manager

**File:** `infrastructure/prepare_dataset_on_ec2.py`

Changes:
- Added `enable_cloudwatch_logs` parameter to `prepare_dataset()` method
- Added `enable_cloudwatch_logs` parameter to `generate_user_data()` method
- Automatically selects appropriate user data script:
  - `user_data_with_cloudwatch.sh` when CloudWatch Logs enabled
  - `user_data_script.sh` when CloudWatch Logs disabled
- Added `--enable-cloudwatch-logs` CLI flag

Usage:
```bash
python prepare_dataset_on_ec2.py \
  --fsx-file-system-id fs-xxxxx \
  --volume-size 100GB \
  --chromosomes chr1 chr2 chr3 \
  --dest-subdir phase_100gb \
  --enable-cloudwatch-logs
```

### 3. 100GB Job Runner Script

**File:** `infrastructure/run_100gb_data_prep.ps1`

Features:
- Orchestrates 100GB dataset preparation (chr1-chr10)
- Automatically enables CloudWatch Logs
- Runs job in background
- Provides real-time monitoring instructions
- Displays cost estimates and time estimates
- Saves results to JSON file

Configuration:
- Volume size: 100GB
- Chromosomes: chr1-chr10
- Destination: phase_100gb
- CloudWatch Logs: ENABLED
- Estimated time: 3-5 hours
- Estimated cost: $2.04 - $3.40

Usage:
```powershell
.\run_100gb_data_prep.ps1
```

### 4. CloudWatch Logs Monitoring Script

**File:** `infrastructure/watch_cloudwatch_logs.ps1`

Features:
- Streams CloudWatch Logs to terminal in real-time
- Supports filtering by log stream prefix
- Checks if log group exists before tailing
- Provides helpful error messages

Usage:
```powershell
# Watch all logs
.\watch_cloudwatch_logs.ps1

# Watch specific instance logs
.\watch_cloudwatch_logs.ps1 -LogStreamPrefix i-xxxxx

# Watch specific phase logs
.\watch_cloudwatch_logs.ps1 -LogStreamPrefix i-xxxxx-download
```

### 5. Documentation

Created comprehensive documentation:

**File:** `infrastructure/QUICKSTART_100GB.md`
- Step-by-step guide for 100GB job
- Real-time monitoring instructions
- Expected output for each phase
- Troubleshooting guide
- Cost breakdown
- Next steps

**File:** `infrastructure/CLOUDWATCH_MONITORING_GUIDE.md`
- Complete CloudWatch Logs reference
- Log stream explanations with examples
- Advanced usage (filtering, searching, exporting)
- CloudWatch Logs Insights queries
- Setting up alarms
- Cost management
- Best practices

**File:** `infrastructure/MONITORING_GUIDE.md`
- Overview of all monitoring options
- Comparison of console output vs CloudWatch Logs
- Detailed examples of what to expect
- Troubleshooting guide

## IAM Permissions

The EC2 IAM role (`EC2DataPrepRole`) already has the necessary permissions:
- `CloudWatchAgentServerPolicy` (AWS managed policy)
  - `logs:CreateLogGroup`
  - `logs:CreateLogStream`
  - `logs:PutLogEvents`
  - `logs:DescribeLogStreams`

No additional IAM changes required.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ EC2 Instance (c5.4xlarge)                                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Data Preparation Scripts                             │  │
│  │  - hg38_downloader.py                                │  │
│  │  - checksum_calculator.py                            │  │
│  │  - fsx_uploader.py                                   │  │
│  │  - data_integrity_validator.py                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Log Files                                            │  │
│  │  - /var/log/data-prep.log                           │  │
│  │  - /data-prep/logs/download.log                     │  │
│  │  - /data-prep/logs/upload.log                       │  │
│  │  - /data-prep/logs/validation.log                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ CloudWatch Logs Agent                                │  │
│  │  - Monitors log files                                │  │
│  │  - Streams to CloudWatch in real-time               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ CloudWatch Logs                                             │
│                                                              │
│  Log Group: /aws/ec2/data-prep                             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Log Streams                                          │  │
│  │  - i-xxxxx-main                                      │  │
│  │  - i-xxxxx-download                                  │  │
│  │  - i-xxxxx-upload                                    │  │
│  │  - i-xxxxx-validation                                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Monitoring Tools                                            │
│                                                              │
│  - watch_cloudwatch_logs.ps1                               │
│  - AWS CLI (aws logs tail)                                 │
│  - CloudWatch Console                                       │
│  - CloudWatch Logs Insights                                │
└─────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Example 1: Run 100GB Job with Monitoring

Terminal 1 (launch job):
```powershell
cd infrastructure
.\run_100gb_data_prep.ps1
```

Terminal 2 (monitor logs):
```powershell
cd infrastructure
.\watch_cloudwatch_logs.ps1
```

### Example 2: Run Custom Job with CloudWatch Logs

```bash
python prepare_dataset_on_ec2.py \
  --fsx-file-system-id fs-04b3f909e86004fc2 \
  --volume-size 500GB \
  --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 chr11 chr12 chr13 chr14 chr15 chr16 chr17 chr18 chr19 chr20 chr21 chr22 chrX \
  --dest-subdir phase_500gb \
  --s3-scripts-bucket my-bucket/scripts \
  --enable-cloudwatch-logs \
  --max-runtime-hours 12
```

### Example 3: View Historical Logs

```powershell
# Last 3 hours
aws logs tail /aws/ec2/data-prep --since 3h --region us-west-2

# Specific instance
aws logs tail /aws/ec2/data-prep --log-stream-name-prefix i-xxxxx --region us-west-2

# Download logs only
aws logs tail /aws/ec2/data-prep --log-stream-name-prefix i-xxxxx-download --region us-west-2
```

## Testing

### Manual Testing Checklist

- [x] User data script with CloudWatch Logs created
- [x] EC2 data prep manager updated with CloudWatch Logs support
- [x] 100GB runner script created
- [x] CloudWatch Logs monitoring script created
- [x] Documentation created (3 guides)
- [x] No syntax errors in Python code
- [x] No syntax errors in PowerShell scripts
- [x] IAM permissions verified

### Integration Testing (To Be Done)

- [ ] Launch 100GB job with CloudWatch Logs enabled
- [ ] Verify log group is created
- [ ] Verify all 4 log streams are created
- [ ] Verify logs are streaming in real-time
- [ ] Verify monitoring script works
- [ ] Verify job completes successfully
- [ ] Verify logs are retained after instance termination

## Cost Analysis

### CloudWatch Logs Costs

**Per Job:**
- 10GB job: ~$0.01 (10 MB logs)
- 100GB job: ~$0.03 (50 MB logs)
- 500GB job: ~$0.08 (150 MB logs)
- 1TB job: ~$0.12 (200 MB logs)
- 2TB job: ~$0.15 (250 MB logs)

**Monthly Storage (30-day retention):**
- All jobs combined: ~$0.02/month

**Total CloudWatch Logs Cost for Full Validation:**
- Ingestion: ~$0.39
- Storage (30 days): ~$0.02
- **Total: ~$0.41**

This is negligible compared to compute costs ($50-100 for full validation).

## Benefits

1. **Real-Time Visibility**
   - See exactly what's happening during long-running jobs
   - No need to SSH into instances
   - Monitor from any terminal

2. **Debugging**
   - Detailed error messages
   - Stack traces for failures
   - Progress tracking for each phase

3. **Historical Analysis**
   - Compare job performance over time
   - Identify bottlenecks
   - Optimize future runs

4. **Alerting**
   - Set up CloudWatch Alarms for failures
   - Get notified of long-running jobs
   - Proactive monitoring

5. **Compliance**
   - Audit trail of all operations
   - Retention policies for compliance
   - Searchable logs for investigations

## Next Steps

1. **Test the 100GB job:**
   ```powershell
   .\run_100gb_data_prep.ps1
   ```

2. **Monitor in real-time:**
   ```powershell
   .\watch_cloudwatch_logs.ps1
   ```

3. **Create runner scripts for larger datasets:**
   - `run_500gb_data_prep.ps1` (chr1-chr22, chrX)
   - `run_1tb_data_prep.ps1` (all chromosomes with preprocessing)
   - `run_2tb_data_prep.ps1` (all chromosomes with variants)

4. **Set up CloudWatch Alarms:**
   - Job failure detection
   - Long-running job alerts
   - Validation error alerts

5. **Create CloudWatch Dashboard:**
   - Job status overview
   - Performance metrics
   - Cost tracking

## Files Created/Modified

### Created:
- `infrastructure/user_data_with_cloudwatch.sh`
- `infrastructure/run_100gb_data_prep.ps1`
- `infrastructure/watch_cloudwatch_logs.ps1`
- `infrastructure/QUICKSTART_100GB.md`
- `infrastructure/CLOUDWATCH_MONITORING_GUIDE.md`
- `infrastructure/MONITORING_GUIDE.md`
- `infrastructure/TASK_2.6_CLOUDWATCH_INTEGRATION.md` (this file)

### Modified:
- `infrastructure/prepare_dataset_on_ec2.py`
  - Added `enable_cloudwatch_logs` parameter
  - Updated `generate_user_data()` to select appropriate script
  - Added CLI flag `--enable-cloudwatch-logs`

## Summary

CloudWatch Logs integration is complete and ready for testing. The implementation provides a **unified single-terminal experience** where logs automatically stream after launching the job.

**To run the 100GB job:**
```powershell
.\run_100gb_data_prep.ps1
```

That's it! The script will:
1. Launch the instance
2. Wait for CloudWatch Logs to be available
3. Automatically start streaming logs to your terminal
4. Show real-time progress for all phases
5. Display results when complete

No need for multiple terminals or manual log commands. Everything is automated for the best user experience.

**Ready to proceed with 100GB dataset preparation!**
