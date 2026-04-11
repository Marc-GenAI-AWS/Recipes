# Quick Relaunch Guide

## What Happened

The current instance (i-05fe66a7bcd77cdcc) has a configuration issue:
- Wrong S3 path in user data script
- Using old c5.4xlarge instance type
- No detailed monitoring enabled

## What's Fixed

✅ **S3 Path Corrected** - `user_data_script.sh` now uses correct path
✅ **c6i.4xlarge Confirmed** - Already set as default (12.5 Gbps network)
✅ **Detailed Monitoring Added** - All new instances get 1-minute CloudWatch metrics
✅ **Monitoring Script Created** - `monitor_instance.ps1` for real-time tracking

## How to Relaunch

### Option 1: Automated (Recommended)

Run the relaunch script - it handles everything:

```powershell
.\infrastructure\relaunch_10gb_job.ps1
```

This will:
1. Terminate the old instance
2. Launch new c6i.4xlarge with correct configuration
3. Provide monitoring links

### Option 2: Manual

1. Terminate old instance:
```powershell
aws ec2 terminate-instances --instance-ids i-05fe66a7bcd77cdcc
```

2. Launch new job:
```powershell
.\infrastructure\run_10gb_data_prep.ps1
```

## Monitor the New Instance

### Real-time Monitoring Script
```powershell
.\infrastructure\monitor_instance.ps1
```

Shows:
- CPU utilization with trend graph
- Network In (download) with rate
- Network Out (upload to FSx) with rate
- Disk operations
- Direct AWS Console links

### AWS Console

With detailed monitoring enabled, you can now see:
- **EC2 Metrics**: CPU, Network, Disk (1-minute intervals)
- **CloudWatch Graphs**: Real-time visualization
- **Network Activity**: Track download/upload progress

The monitoring script provides direct links to both.

## What to Expect

### Timeline
- **0-5 min**: Instance launch and initialization
- **5-30 min**: Download chr1 and chr2 (~10GB)
- **30-45 min**: Upload to FSx and validation
- **45-50 min**: Cleanup and auto-termination

### Network Activity
- **Download phase**: Should see 50-100 MB/s (c6i network)
- **Upload phase**: Should see ~100 MB/s (FSx 1024 MB/s throughput)
- **CPU**: Will spike during checksum calculation

### Success Indicators
- Network In increases steadily during download
- Network Out increases during FSx upload
- CPU spikes during checksum validation
- Instance auto-terminates when complete

## Troubleshooting

### If download is slow
- Check Network In metrics - should be 50-100 MB/s
- UCSC servers may be rate-limiting
- c6i.4xlarge supports up to 1,562 MB/s

### If upload is slow
- Check Network Out metrics - should be ~100 MB/s
- FSx throughput is 1,024 MB/s (128 MB/s per client)
- Same-AZ transfer is fast and free

### If instance is idle
- Run `monitor_instance.ps1` to check metrics
- Check console output for errors
- Verify S3 scripts bucket is accessible

## Cost

- **c6i.4xlarge**: ~$0.68/hour
- **Detailed monitoring**: ~$2.10/month (~$0.003/hour)
- **10GB job**: ~$0.34-$0.68 total
- **Data transfer**: $0 (same-AZ)

## Next Steps After Success

1. Verify data on FSx: `/mnt/fsx/phase_10gb/`
2. Check validation logs: `/mnt/fsx/phase_10gb/logs/`
3. Run 100GB dataset: `.\infrastructure\run_100gb_data_prep.ps1`
4. Eventually run 2TB dataset for full validation
