# Quick Monitoring Commands Reference

Quick reference for monitoring your running data preparation jobs.

## Check Overall Progress

**Best option - Shows everything:**
```powershell
.\check_job_progress.ps1
```

This shows:
- Instance state and elapsed time
- Recent console output (last 50 lines)
- FSx storage usage
- Progress checklist (which phases are complete)
- Current status estimate

**Auto-detects running instances** - no need to specify instance ID!

## Check FSx Data Transfer

**See if data is actually being written to FSx:**
```powershell
.\check_fsx_data.ps1
```

This shows:
- FSx volume information
- Storage used
- Write operations (last 30 minutes)
- Data throughput (MB/GB written)
- Whether data is actively being transferred

## Monitor Console Output Continuously

**Watch console output in real-time:**
```powershell
.\monitor_data_prep.ps1 -InstanceId i-xxxxx
```

Refreshes every 30 seconds with color-coded output.

## Watch CloudWatch Logs (100GB+ jobs)

**Stream CloudWatch Logs:**
```powershell
aws logs tail /aws/ec2/data-prep --follow --region us-west-2
```

**Or use the script:**
```powershell
.\watch_cloudwatch_logs.ps1
```

## Quick AWS CLI Commands

**Get instance ID:**
```powershell
aws ec2 describe-instances --region us-west-2 --filters "Name=tag:Name,Values=data-prep-*" "Name=instance-state-name,Values=running" --query "Reservations[*].Instances[*].InstanceId" --output text
```

**Get console output:**
```powershell
aws ec2 get-console-output --instance-id i-xxxxx --region us-west-2 --output text
```

**Check instance state:**
```powershell
aws ec2 describe-instances --instance-ids i-xxxxx --region us-west-2 --query "Reservations[0].Instances[0].State.Name" --output text
```

**Check FSx metrics:**
```powershell
# Storage used
aws cloudwatch get-metric-statistics --namespace AWS/FSx --metric-name StorageUsed --dimensions Name=FileSystemId,Value=fs-04b3f909e86004fc2 --start-time 2024-04-10T00:00:00Z --end-time 2024-04-10T23:59:59Z --period 3600 --statistics Average --region us-west-2

# Write operations
aws cloudwatch get-metric-statistics --namespace AWS/FSx --metric-name DataWriteOperations --dimensions Name=FileSystemId,Value=fs-04b3f909e86004fc2 --start-time 2024-04-10T00:00:00Z --end-time 2024-04-10T23:59:59Z --period 3600 --statistics Sum --region us-west-2
```

## What to Look For

### During Download Phase (20-40 minutes)
Console output should show:
```
Downloading hg38 Chromosome Data
Downloading chr1.fa.gz...
Progress: 25%
Progress: 50%
```

**FSx activity:** None yet (data is being downloaded to EC2 local storage)

### During Upload Phase (10-30 minutes)
Console output should show:
```
Uploading Data to FSx
Uploading chr1.fa.gz...
Progress: 25%
```

**FSx activity:** High write operations and data throughput

### During Validation Phase (5-15 minutes)
Console output should show:
```
Validating Data Integrity
Validating file 1/10: chr1.fa.gz
✓ Size match
✓ MD5 match
```

**FSx activity:** Read operations (not shown in write metrics)

## Troubleshooting

### "No console output available"
- Instance is still launching (wait 2-3 minutes)
- Run: `.\check_job_progress.ps1` to see instance state

### "No write activity detected"
- Download phase is still in progress (data not uploaded yet)
- CloudWatch metrics have 5-minute delay
- Check console output to see current phase

### "Instance not found"
- Instance may have terminated (check for results file)
- Specify instance ID: `.\check_job_progress.ps1 -InstanceId i-xxxxx`

## Timeline for 10GB Job

| Phase | Duration | What to Monitor |
|-------|----------|-----------------|
| Launch | 2-5 min | Instance state |
| Setup | 5-10 min | Console output |
| Download | 20-30 min | Console output (progress %) |
| Checksum | 2-5 min | Console output |
| Upload | 10-15 min | FSx write metrics, console output |
| Validation | 5-10 min | Console output |
| Cleanup | 2-5 min | Console output |
| **Total** | **45-80 min** | |

## Timeline for 100GB Job

| Phase | Duration | What to Monitor |
|-------|----------|-----------------|
| Launch | 2-5 min | Instance state |
| Setup | 5-10 min | CloudWatch Logs |
| Download | 2-3 hours | CloudWatch Logs (download stream) |
| Checksum | 5-10 min | CloudWatch Logs |
| Upload | 30-60 min | FSx write metrics, CloudWatch Logs |
| Validation | 10-15 min | CloudWatch Logs (validation stream) |
| Cleanup | 2-5 min | CloudWatch Logs |
| **Total** | **3-5 hours** | |

## Quick Decision Tree

**Want to see overall progress?**
→ `.\check_job_progress.ps1`

**Want to confirm data is reaching FSx?**
→ `.\check_fsx_data.ps1`

**Want to watch in real-time?**
→ `.\monitor_data_prep.ps1 -InstanceId i-xxxxx` (10GB job)
→ `aws logs tail /aws/ec2/data-prep --follow --region us-west-2` (100GB job)

**Job seems stuck?**
→ Check console output for errors
→ Check FSx metrics for activity
→ Verify instance is still running

**Job completed?**
→ Check for `results_*gb_*.json` file
→ Look for "Data Preparation Completed Successfully" in console output
