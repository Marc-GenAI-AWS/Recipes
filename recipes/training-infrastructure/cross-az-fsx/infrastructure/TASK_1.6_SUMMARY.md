# Task 1.6: Enable CloudWatch Monitoring for FSx Volume

## Summary

Successfully enabled CloudWatch monitoring for the FSx NetApp ONTAP volume with comprehensive alarms for performance tracking during cross-AZ validation testing.

## Implementation Details

### CloudWatch Alarms Created

Four CloudWatch alarms have been configured to monitor critical FSx performance metrics:

1. **Network Throughput Alarm** (`fsx-cross-az-network-throughput-high`)
   - Metric: `NetworkThroughputUtilization`
   - Threshold: 80%
   - Triggers when network throughput utilization exceeds 80% for 2 consecutive 5-minute periods
   - Critical for monitoring cross-AZ data transfer performance

2. **CPU Utilization Alarm** (`fsx-cross-az-cpu-utilization-high`)
   - Metric: `CPUUtilization`
   - Threshold: 80%
   - Triggers when CPU utilization exceeds 80% for 2 consecutive 5-minute periods
   - Helps identify processing bottlenecks during training data access

3. **Disk Throughput Balance Alarm** (`fsx-cross-az-disk-throughput-balance-low`)
   - Metric: `FileServerDiskThroughputBalance`
   - Threshold: 20%
   - Triggers when burst credit balance falls below 20% for 2 consecutive 5-minute periods
   - Important for systems with throughput capacity < 512 MBps
   - Configured with `TreatMissingData.NOT_BREACHING` to avoid false alarms

4. **Disk IOPS Utilization Alarm** (`fsx-cross-az-disk-iops-utilization-high`)
   - Metric: `FileServerDiskIopsUtilization`
   - Threshold: 80%
   - Triggers when disk IOPS utilization exceeds 80% for 2 consecutive 5-minute periods
   - Monitors I/O performance for genomic data access patterns

### Automatic Metrics Collection

FSx for NetApp ONTAP automatically sends metrics to CloudWatch:
- **Default interval**: 1-minute periods for most metrics
- **Namespace**: `AWS/FSx`
- **Dimension**: `FileSystemId`
- **Retention**: 15 months of historical data

Key metrics automatically collected include:
- `NetworkThroughputUtilization`
- `NetworkSentBytes` / `NetworkReceivedBytes`
- `DataReadBytes` / `DataWriteBytes`
- `DataReadOperations` / `DataWriteOperations`
- `CPUUtilization`
- `FileServerDiskThroughputUtilization`
- `FileServerDiskIopsUtilization`
- `StorageUsed` / `LogicalDataStored`

### CloudWatch Dashboard Access

A CloudWatch dashboard URL output has been added to the stack for easy access to FSx metrics visualization.

## Files Modified

1. **infrastructure/stacks/fsx_stack.py**
   - Added `aws_cloudwatch` import
   - Created 4 CloudWatch alarms for FSx monitoring
   - Added `CloudWatchDashboardUrl` output

2. **infrastructure/tests/test_fsx_stack.py**
   - Added `test_cloudwatch_alarms_created()` to verify alarm creation
   - Added `test_cloudwatch_alarm_metrics()` to verify correct metric configuration
   - Updated `test_fsx_outputs_exist()` to include CloudWatch dashboard URL

## Testing

All unit tests pass successfully:
```
tests/test_fsx_stack.py::test_fsx_file_system_created PASSED
tests/test_fsx_stack.py::test_fsx_storage_virtual_machine_created PASSED
tests/test_fsx_stack.py::test_fsx_volume_created PASSED
tests/test_fsx_stack.py::test_fsx_outputs_exist PASSED
tests/test_fsx_stack.py::test_cloudwatch_alarms_created PASSED
tests/test_fsx_stack.py::test_cloudwatch_alarm_metrics PASSED
```

CDK synthesis completed successfully with no errors.

## Deployment

To deploy the updated monitoring configuration:

```bash
cd infrastructure
./deploy.sh
```

The deployment will:
1. Update the FSx stack with CloudWatch alarms
2. Create the 4 monitoring alarms in CloudWatch
3. Output the CloudWatch dashboard URL for metrics visualization

## Monitoring Access

After deployment, you can access FSx metrics through:

1. **AWS Console**:
   - Navigate to CloudWatch → Alarms to view alarm status
   - Navigate to CloudWatch → Metrics → AWS/FSx to view detailed metrics
   - Use the CloudWatch dashboard URL from stack outputs

2. **AWS CLI**:
   ```bash
   # View alarm status
   aws cloudwatch describe-alarms --alarm-name-prefix "fsx-cross-az"
   
   # Get FSx metrics
   aws cloudwatch get-metric-statistics \
     --namespace AWS/FSx \
     --metric-name NetworkThroughputUtilization \
     --dimensions Name=FileSystemId,Value=<file-system-id> \
     --start-time 2024-01-01T00:00:00Z \
     --end-time 2024-01-01T01:00:00Z \
     --period 300 \
     --statistics Average
   ```

## Validation Use Cases

These alarms support the validation requirements:

- **Requirement 4 (Network Performance Measurement)**: Network throughput alarm monitors cross-AZ data transfer performance
- **Requirement 3 (Incremental Data Volume Validation)**: All alarms help identify performance degradation as data volume scales from 10GB to 2TB
- **Requirement 8 (Failure Scenarios)**: Alarms provide early detection of FSx performance issues during failure scenario testing

## Next Steps

- Task 1.7: Verify P5 instance availability in us-west-2b
- Phase 2: Begin data preparation with hg38 chromosome data download

## References

- [AWS FSx CloudWatch Monitoring Documentation](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html)
- [FSx File System Metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-metrics.html)
- [Creating CloudWatch Alarms for FSx](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/creating_alarms.html)
