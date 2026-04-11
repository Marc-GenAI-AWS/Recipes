#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Monitor EC2 instance CPU, network, and disk activity
.DESCRIPTION
    Displays real-time metrics for the data preparation EC2 instance
    Enables detailed monitoring if not already enabled
.PARAMETER InstanceId
    EC2 instance ID to monitor (optional, will find latest if not provided)
#>

param(
    [string]$InstanceId = ""
)

# Find the latest data prep instance if not provided
if ([string]::IsNullOrEmpty($InstanceId)) {
    Write-Host "Finding latest data prep instance..." -ForegroundColor Cyan
    $instances = aws ec2 describe-instances `
        --filters "Name=tag:ManagedBy,Values=EC2DataPrepManager" "Name=instance-state-name,Values=running,pending" `
        --query 'Reservations[*].Instances[*].[InstanceId, LaunchTime, State.Name, Tags[?Key==`Name`].Value | [0]]' `
        --output json | ConvertFrom-Json
    
    if ($instances.Count -eq 0) {
        Write-Host "No running data prep instances found" -ForegroundColor Red
        exit 1
    }
    
    # Get the most recent instance
    $latestInstance = $instances | Sort-Object { $_[1] } -Descending | Select-Object -First 1
    $InstanceId = $latestInstance[0]
    $instanceName = $latestInstance[3]
    $launchTime = $latestInstance[1]
    
    Write-Host "Found instance: $InstanceId ($instanceName)" -ForegroundColor Green
    Write-Host "Launched: $launchTime" -ForegroundColor Gray
}

# Check if detailed monitoring is enabled
Write-Host "`nChecking monitoring status..." -ForegroundColor Cyan
$monitoringState = aws ec2 describe-instances `
    --instance-ids $InstanceId `
    --query 'Reservations[0].Instances[0].Monitoring.State' `
    --output text

if ($monitoringState -eq "disabled") {
    Write-Host "Detailed monitoring is DISABLED (5-minute intervals)" -ForegroundColor Yellow
    Write-Host "Enabling detailed monitoring (1-minute intervals)..." -ForegroundColor Cyan
    aws ec2 monitor-instances --instance-ids $InstanceId | Out-Null
    Write-Host "Detailed monitoring enabled! Metrics will appear in AWS Console in ~1 minute" -ForegroundColor Green
    Write-Host "Note: Detailed monitoring costs ~$2.10/month per instance" -ForegroundColor Gray
} else {
    Write-Host "Detailed monitoring is ENABLED (1-minute intervals)" -ForegroundColor Green
}

# Get instance details
Write-Host "`nInstance Details:" -ForegroundColor Cyan
$instanceInfo = aws ec2 describe-instances `
    --instance-ids $InstanceId `
    --query 'Reservations[0].Instances[0].[InstanceType, Placement.AvailabilityZone, State.Name, PrivateIpAddress, PublicIpAddress]' `
    --output json | ConvertFrom-Json

Write-Host "  Instance Type: $($instanceInfo[0])" -ForegroundColor White
Write-Host "  Availability Zone: $($instanceInfo[1])" -ForegroundColor White
Write-Host "  State: $($instanceInfo[2])" -ForegroundColor White
Write-Host "  Private IP: $($instanceInfo[3])" -ForegroundColor White
Write-Host "  Public IP: $($instanceInfo[4])" -ForegroundColor White

# Function to get metrics
function Get-InstanceMetrics {
    param(
        [string]$MetricName,
        [string]$Statistic = "Average",
        [int]$Minutes = 15
    )
    
    $endTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss")
    $startTime = (Get-Date).AddMinutes(-$Minutes).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss")
    
    $metrics = aws cloudwatch get-metric-statistics `
        --namespace AWS/EC2 `
        --metric-name $MetricName `
        --dimensions Name=InstanceId,Value=$InstanceId `
        --start-time $startTime `
        --end-time $endTime `
        --period 60 `
        --statistics $Statistic `
        --query 'Datapoints | sort_by(@, &Timestamp)' `
        --output json | ConvertFrom-Json
    
    return $metrics
}

# Display metrics
Write-Host "`n=== METRICS (Last 15 minutes) ===" -ForegroundColor Cyan

# CPU Utilization
Write-Host "`nCPU Utilization:" -ForegroundColor Yellow
$cpuMetrics = Get-InstanceMetrics -MetricName "CPUUtilization" -Statistic "Average"
if ($cpuMetrics.Count -gt 0) {
    $latestCpu = $cpuMetrics[-1]
    $avgCpu = ($cpuMetrics | Measure-Object -Property Average -Average).Average
    Write-Host "  Current: $([math]::Round($latestCpu.Average, 2))%" -ForegroundColor White
    Write-Host "  Average: $([math]::Round($avgCpu, 2))%" -ForegroundColor White
    
    # Show trend
    Write-Host "  Trend: " -NoNewline -ForegroundColor White
    foreach ($metric in $cpuMetrics[-10..-1]) {
        $bar = [math]::Round($metric.Average / 10)
        Write-Host ("█" * $bar) -NoNewline -ForegroundColor Green
    }
    Write-Host ""
} else {
    Write-Host "  No data available yet (wait ~1 minute after enabling detailed monitoring)" -ForegroundColor Gray
}

# Network In (Download)
Write-Host "`nNetwork In (Download):" -ForegroundColor Yellow
$networkInMetrics = Get-InstanceMetrics -MetricName "NetworkIn" -Statistic "Sum"
if ($networkInMetrics.Count -gt 0) {
    $totalBytes = ($networkInMetrics | Measure-Object -Property Sum -Sum).Sum
    $totalMB = [math]::Round($totalBytes / 1MB, 2)
    $totalGB = [math]::Round($totalBytes / 1GB, 2)
    
    Write-Host "  Total downloaded: $totalMB MB ($totalGB GB)" -ForegroundColor White
    
    # Calculate rate from last few data points
    if ($networkInMetrics.Count -ge 2) {
        $recent = $networkInMetrics[-5..-1]
        $recentBytes = ($recent | Measure-Object -Property Sum -Sum).Sum
        $recentMinutes = $recent.Count
        $rateMBps = [math]::Round(($recentBytes / 1MB) / $recentMinutes, 2)
        Write-Host "  Recent rate: $rateMBps MB/min" -ForegroundColor White
    }
} else {
    Write-Host "  No data available yet" -ForegroundColor Gray
}

# Network Out (Upload to FSx)
Write-Host "`nNetwork Out (Upload to FSx):" -ForegroundColor Yellow
$networkOutMetrics = Get-InstanceMetrics -MetricName "NetworkOut" -Statistic "Sum"
if ($networkOutMetrics.Count -gt 0) {
    $totalBytes = ($networkOutMetrics | Measure-Object -Property Sum -Sum).Sum
    $totalMB = [math]::Round($totalBytes / 1MB, 2)
    $totalGB = [math]::Round($totalBytes / 1GB, 2)
    
    Write-Host "  Total uploaded: $totalMB MB ($totalGB GB)" -ForegroundColor White
    
    # Calculate rate
    if ($networkOutMetrics.Count -ge 2) {
        $recent = $networkOutMetrics[-5..-1]
        $recentBytes = ($recent | Measure-Object -Property Sum -Sum).Sum
        $recentMinutes = $recent.Count
        $rateMBps = [math]::Round(($recentBytes / 1MB) / $recentMinutes, 2)
        Write-Host "  Recent rate: $rateMBps MB/min" -ForegroundColor White
    }
} else {
    Write-Host "  No data available yet" -ForegroundColor Gray
}

# Disk Read/Write
Write-Host "`nDisk Operations:" -ForegroundColor Yellow
$diskReadMetrics = Get-InstanceMetrics -MetricName "DiskReadBytes" -Statistic "Sum"
$diskWriteMetrics = Get-InstanceMetrics -MetricName "DiskWriteBytes" -Statistic "Sum"

if ($diskReadMetrics.Count -gt 0) {
    $totalRead = ($diskReadMetrics | Measure-Object -Property Sum -Sum).Sum
    $totalReadMB = [math]::Round($totalRead / 1MB, 2)
    Write-Host "  Total read: $totalReadMB MB" -ForegroundColor White
}

if ($diskWriteMetrics.Count -gt 0) {
    $totalWrite = ($diskWriteMetrics | Measure-Object -Property Sum -Sum).Sum
    $totalWriteMB = [math]::Round($totalWrite / 1MB, 2)
    Write-Host "  Total write: $totalWriteMB MB" -ForegroundColor White
}

# AWS Console Links
Write-Host "`n=== AWS CONSOLE LINKS ===" -ForegroundColor Cyan
$region = "us-west-2"
Write-Host "Instance Monitoring:" -ForegroundColor Yellow
Write-Host "  https://console.aws.amazon.com/ec2/v2/home?region=$region#InstanceDetails:instanceId=$InstanceId" -ForegroundColor Blue

Write-Host "`nCloudWatch Metrics:" -ForegroundColor Yellow
Write-Host "  https://console.aws.amazon.com/cloudwatch/home?region=$region#metricsV2:graph=~();query=~'*7bNamespace*3d*27AWS*2fEC2*27*2cMetricName*3d*27CPUUtilization*27*2cInstanceId*3d*27$InstanceId*27*7d" -ForegroundColor Blue

Write-Host "`n=== REFRESH ===" -ForegroundColor Cyan
Write-Host "Run this script again to see updated metrics" -ForegroundColor White
Write-Host "  .\monitor_instance.ps1 -InstanceId $InstanceId" -ForegroundColor Gray
