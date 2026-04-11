# CloudWatch Logs Monitoring Guide

Complete guide for monitoring data preparation jobs using CloudWatch Logs.

## Overview

CloudWatch Logs provides real-time streaming of logs from your EC2 data preparation instances. This gives you full visibility into:
- Download progress for each chromosome
- Upload progress to FSx
- Validation results
- Errors and warnings
- Performance metrics

## Architecture

```
EC2 Instance
├── /var/log/data-prep.log          → CloudWatch: {instance-id}-main
├── /data-prep/logs/download.log    → CloudWatch: {instance-id}-download
├── /data-prep/logs/upload.log      → CloudWatch: {instance-id}-upload
└── /data-prep/logs/validation.log  → CloudWatch: {instance-id}-validation
```

All logs are streamed to the CloudWatch Log Group: `/aws/ec2/data-prep`

## Quick Start

### 1. Enable CloudWatch Logs

CloudWatch Logs are automatically enabled when you use:
- `run_100gb_data_prep.ps1` (includes `--enable-cloudwatch-logs`)
- Any job with the `--enable-cloudwatch-logs` flag

### 2. Watch Logs in Real-Time

**Option A: Use the monitoring script**
```powershell
.\watch_cloudwatch_logs.ps1
```

**Option B: Use AWS CLI directly**
```powershell
aws logs tail /aws/ec2/data-prep --follow --region us-west-2
```

**Option C: Watch a specific log stream**
```powershell
# Replace i-xxxxx with your instance ID
aws logs tail /aws/ec2/data-prep --follow --region us-west-2 --log-stream-name-prefix i-xxxxx-download
```

## Log Streams Explained

### Main Log Stream: `{instance-id}-main`

Contains the overall execution flow:
- Instance configuration
- CloudWatch agent setup
- FSx mount operations
- Phase transitions
- Completion status

**Example:**
```
========================================
EC2 Data Preparation Script Started
Time: 2024-04-10 14:30:22
========================================

Configuration:
  Instance ID: i-0a1b2c3d4e5f6g7h8
  FSX_DNS_NAME: svm-xxxxx.fs-xxxxx.fsx.us-west-2.amazonaws.com
  CHROMOSOMES: chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10
  DEST_SUBDIR: phase_100gb
  VOLUME_SIZE: 100GB

✓ CloudWatch Logs agent started
✓ FSx volume mounted successfully
✓ Download completed
✓ Upload completed
✓ Validation completed

========================================
Data Preparation Completed Successfully
========================================
```

### Download Log Stream: `{instance-id}-download`

Contains detailed download progress:
- URL for each chromosome
- File sizes
- Download progress
- MD5 checksums from UCSC
- Retry attempts

**Example:**
```
Downloading chr1.fa.gz...
  URL: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/chr1.fa.gz
  Size: 248.96 MB
  Progress: 0%
  Progress: 25%
  Progress: 50%
  Progress: 75%
  Progress: 100%
  ✓ Downloaded successfully
  MD5: abc123def456...

Downloading chr2.fa.gz...
  URL: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/chr2.fa.gz
  Size: 242.19 MB
  Progress: 0%
  Progress: 25%
  ...
```

### Upload Log Stream: `{instance-id}-upload`

Contains detailed upload progress:
- Source and destination paths
- File sizes
- Upload progress
- Transfer rates
- Retry attempts

**Example:**
```
Uploading to FSx: /mnt/fsx/phase_100gb

Uploading chr1.fa.gz...
  Source: /data-prep/hg38_data/chr1.fa.gz
  Destination: /mnt/fsx/phase_100gb/chr1.fa.gz
  Size: 248.96 MB
  Progress: 0%
  Progress: 25%
  Progress: 50%
  Progress: 75%
  Progress: 100%
  ✓ Uploaded successfully
  Transfer rate: 45.2 MB/s

Uploading chr2.fa.gz...
  ...
```

### Validation Log Stream: `{instance-id}-validation`

Contains detailed validation results:
- File-by-file validation
- Size comparisons
- MD5 checksum comparisons
- SHA256 checksum comparisons
- Validation summary

**Example:**
```
Validating data integrity...

File 1/10: chr1.fa.gz
  Source size: 248956422 bytes
  FSx size: 248956422 bytes
  ✓ Size match

  Source MD5: abc123def456...
  FSx MD5: abc123def456...
  ✓ MD5 match

  Source SHA256: xyz789uvw012...
  FSx SHA256: xyz789uvw012...
  ✓ SHA256 match

File 2/10: chr2.fa.gz
  ...

========================================
Validation Summary
========================================
Total files: 10
Valid: 10
Invalid: 0
Total size: 1.2 GB
Duration: 12.3 minutes

✓ All files validated successfully
```

## Advanced Usage

### Filter Logs by Pattern

**Find all errors:**
```powershell
aws logs filter-log-events `
  --log-group-name /aws/ec2/data-prep `
  --filter-pattern "ERROR" `
  --region us-west-2
```

**Find download progress:**
```powershell
aws logs filter-log-events `
  --log-group-name /aws/ec2/data-prep `
  --filter-pattern "Progress:" `
  --region us-west-2
```

**Find validation results:**
```powershell
aws logs filter-log-events `
  --log-group-name /aws/ec2/data-prep `
  --filter-pattern "✓" `
  --region us-west-2
```

### View Historical Logs

**Last 3 hours:**
```powershell
aws logs tail /aws/ec2/data-prep --since 3h --region us-west-2
```

**Last 24 hours:**
```powershell
aws logs tail /aws/ec2/data-prep --since 24h --region us-west-2
```

**Specific time range:**
```powershell
aws logs filter-log-events `
  --log-group-name /aws/ec2/data-prep `
  --start-time 1712764800000 `
  --end-time 1712851200000 `
  --region us-west-2
```

### Export Logs to File

**Export all logs:**
```powershell
aws logs tail /aws/ec2/data-prep --region us-west-2 > data-prep-logs.txt
```

**Export specific stream:**
```powershell
aws logs tail /aws/ec2/data-prep `
  --log-stream-name-prefix i-xxxxx-download `
  --region us-west-2 > download-logs.txt
```

### Search Across Multiple Jobs

**Find all completed jobs:**
```powershell
aws logs filter-log-events `
  --log-group-name /aws/ec2/data-prep `
  --filter-pattern "Data Preparation Completed Successfully" `
  --region us-west-2
```

**Find all failed jobs:**
```powershell
aws logs filter-log-events `
  --log-group-name /aws/ec2/data-prep `
  --filter-pattern "ERROR" `
  --region us-west-2
```

## CloudWatch Logs Insights

For advanced analysis, use CloudWatch Logs Insights queries:

### Query 1: Job Duration Analysis

```sql
fields @timestamp, @message
| filter @message like /Data Preparation Completed Successfully/
| parse @message /Duration: (?<duration>[\d.]+) minutes/
| stats avg(duration) as avg_duration, max(duration) as max_duration, min(duration) as min_duration
```

### Query 2: Download Performance

```sql
fields @timestamp, @message
| filter @message like /Transfer rate/
| parse @message /Transfer rate: (?<rate>[\d.]+) MB\/s/
| stats avg(rate) as avg_rate, max(rate) as max_rate, min(rate) as min_rate
```

### Query 3: Error Analysis

```sql
fields @timestamp, @message
| filter @message like /ERROR/
| stats count() by @message
| sort count desc
```

### Query 4: Validation Failures

```sql
fields @timestamp, @message
| filter @message like /✗/ or @message like /Invalid/
| display @timestamp, @message
```

## Setting Up CloudWatch Alarms

### Alarm 1: Job Failure Detection

```powershell
aws cloudwatch put-metric-alarm `
  --alarm-name "DataPrepJobFailure" `
  --alarm-description "Alert when data prep job fails" `
  --metric-name "Errors" `
  --namespace "AWS/Logs" `
  --statistic "Sum" `
  --period 300 `
  --threshold 1 `
  --comparison-operator "GreaterThanThreshold" `
  --evaluation-periods 1 `
  --region us-west-2
```

### Alarm 2: Long-Running Job

```powershell
aws cloudwatch put-metric-alarm `
  --alarm-name "DataPrepJobTimeout" `
  --alarm-description "Alert when job exceeds expected duration" `
  --metric-name "Duration" `
  --namespace "DataPrep" `
  --statistic "Maximum" `
  --period 3600 `
  --threshold 21600 `
  --comparison-operator "GreaterThanThreshold" `
  --evaluation-periods 1 `
  --region us-west-2
```

## Cost Management

### Log Retention

By default, logs are retained indefinitely. To reduce costs, set a retention period:

```powershell
aws logs put-retention-policy `
  --log-group-name /aws/ec2/data-prep `
  --retention-in-days 30 `
  --region us-west-2
```

**Retention options:**
- 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653 days
- Or never expire (default)

### Cost Estimation

**CloudWatch Logs Pricing (us-west-2):**
- Ingestion: $0.50 per GB
- Storage: $0.03 per GB per month
- Insights queries: $0.005 per GB scanned

**Example: 100GB Job**
- Log data: ~50 MB
- Ingestion cost: 0.05 GB × $0.50 = $0.025
- Storage cost (30 days): 0.05 GB × $0.03 = $0.0015
- **Total: ~$0.027**

**Example: 2TB Job**
- Log data: ~200 MB
- Ingestion cost: 0.2 GB × $0.50 = $0.10
- Storage cost (30 days): 0.2 GB × $0.03 = $0.006
- **Total: ~$0.106**

## Troubleshooting

### Issue: "Log group not found"

**Cause:** The log group is created when the CloudWatch agent first writes logs.

**Solution:** Wait 2-3 minutes after instance launch and try again.

### Issue: "No log streams found"

**Cause:** The instance hasn't started logging yet, or the CloudWatch agent failed to start.

**Solution:**
1. Check instance state: `aws ec2 describe-instances --instance-ids i-xxxxx`
2. Check console output: `aws ec2 get-console-output --instance-id i-xxxxx`
3. Verify IAM role has CloudWatch permissions

### Issue: Logs stop updating

**Cause:** Instance terminated or CloudWatch agent crashed.

**Solution:**
1. Check instance state
2. Check console output for errors
3. Review the last log entries for error messages

### Issue: "Access Denied" when viewing logs

**Cause:** Your IAM user/role doesn't have CloudWatch Logs permissions.

**Solution:** Add the following policy to your IAM user/role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
        "logs:TailLogStream"
      ],
      "Resource": "arn:aws:logs:us-west-2:*:log-group:/aws/ec2/data-prep:*"
    }
  ]
}
```

## Best Practices

1. **Always enable CloudWatch Logs for jobs > 10GB**
   - Provides visibility into long-running jobs
   - Essential for debugging failures
   - Minimal cost impact

2. **Use separate log streams for different phases**
   - Makes it easier to find specific information
   - Reduces noise when debugging
   - Allows parallel analysis

3. **Set appropriate retention periods**
   - 30 days for development/testing
   - 90 days for production
   - 365 days for compliance

4. **Create CloudWatch dashboards**
   - Visualize job progress
   - Track performance trends
   - Monitor costs

5. **Set up alarms for critical events**
   - Job failures
   - Long-running jobs
   - Validation errors

## Summary

CloudWatch Logs provides comprehensive monitoring for data preparation jobs:

✅ Real-time log streaming
✅ Separate streams for each phase
✅ Historical log retention
✅ Advanced search and filtering
✅ Integration with CloudWatch Alarms
✅ Cost-effective (~$0.03 per 100GB job)

For the best monitoring experience:
1. Enable CloudWatch Logs for all jobs > 10GB
2. Use `watch_cloudwatch_logs.ps1` for real-time monitoring
3. Set up retention policies to manage costs
4. Create alarms for critical events
5. Use Logs Insights for advanced analysis

You now have full visibility into your data preparation pipeline!
