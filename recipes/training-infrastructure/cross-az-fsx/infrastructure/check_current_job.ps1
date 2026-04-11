# Quick check for the currently running data prep job

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Current Data Prep Job Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Find running instances with data-prep tag
Write-Host "Looking for running data prep instances..." -ForegroundColor Yellow
$instances = aws ec2 describe-instances `
    --region us-west-2 `
    --filters "Name=tag:Name,Values=data-prep-*" "Name=instance-state-name,Values=running,pending" `
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,LaunchTime,Tags[?Key==`Name`].Value|[0]]' `
    --output text

if ([string]::IsNullOrEmpty($instances)) {
    Write-Host "No running data prep instances found" -ForegroundColor Yellow
    exit 0
}

Write-Host "Found instances:" -ForegroundColor Green
$instances

$instanceLines = $instances -split "`n"
$latestInstance = ($instanceLines | Select-Object -First 1) -split "`t"
$instanceId = $latestInstance[0]

Write-Host ""
Write-Host "Latest instance: $instanceId" -ForegroundColor Cyan
Write-Host ""

# Get console output
Write-Host "Recent console output:" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray
aws ec2 get-console-output --instance-id $instanceId --region us-west-2 --output text | Select-Object -Last 30
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""

# Check FSx metrics
Write-Host "FSx write activity (last 5 minutes):" -ForegroundColor Yellow
$endTime = (Get-Date).ToUniversalTime()
$startTime = $endTime.AddMinutes(-5)

$metrics = aws cloudwatch get-metric-statistics `
    --namespace AWS/FSx `
    --metric-name DataWriteBytes `
    --dimensions Name=FileSystemId,Value=fs-04b3f909e86004fc2 `
    --start-time $startTime.ToString("yyyy-MM-ddTHH:mm:ss") `
    --end-time $endTime.ToString("yyyy-MM-ddTHH:mm:ss") `
    --period 300 `
    --statistics Sum `
    --region us-west-2 `
    --output json | ConvertFrom-Json

if ($metrics.Datapoints.Count -gt 0) {
    $totalBytes = ($metrics.Datapoints | Measure-Object -Property Sum -Sum).Sum
    $totalMB = [math]::Round($totalBytes / 1MB, 2)
    Write-Host "  Data written: $totalMB MB" -ForegroundColor Green
} else {
    Write-Host "  No write activity detected yet" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Quick Commands:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Full console output:" -ForegroundColor White
Write-Host "    aws ec2 get-console-output --instance-id $instanceId --region us-west-2 --output text" -ForegroundColor Gray
Write-Host ""
Write-Host "  Terminate instance:" -ForegroundColor White
Write-Host "    aws ec2 terminate-instances --instance-ids $instanceId --region us-west-2" -ForegroundColor Gray
Write-Host ""
