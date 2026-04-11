# Simple script to check FSx data transfer activity
# Uses direct AWS CLI commands

param(
    [Parameter(Mandatory=$false)]
    [string]$FsxFileSystemId = "fs-04b3f909e86004fc2",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FSx Data Transfer Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "File System: $FsxFileSystemId" -ForegroundColor White
Write-Host "Region: $Region" -ForegroundColor White
Write-Host ""

# Get current time for metrics query
$endTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$startTime = (Get-Date).AddMinutes(-30).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

Write-Host "Checking write operations (last 30 minutes)..." -ForegroundColor Yellow
Write-Host ""

# Get write operations metric
$writeOps = aws cloudwatch get-metric-statistics `
    --namespace AWS/FSx `
    --metric-name DataWriteOperations `
    --dimensions Name=FileSystemId,Value=$FsxFileSystemId `
    --start-time $startTime `
    --end-time $endTime `
    --period 300 `
    --statistics Sum `
    --region $Region `
    --output json 2>$null

if ($LASTEXITCODE -eq 0) {
    $data = $writeOps | ConvertFrom-Json
    
    if ($data.Datapoints.Count -gt 0) {
        Write-Host "Write Operations Detected:" -ForegroundColor Green
        
        $sortedPoints = $data.Datapoints | Sort-Object Timestamp -Descending | Select-Object -First 6
        
        foreach ($point in $sortedPoints) {
            $time = ([DateTime]$point.Timestamp).ToLocalTime().ToString("HH:mm:ss")
            $ops = [math]::Round($point.Sum, 0)
            Write-Host "  $time : $ops operations" -ForegroundColor White
        }
        
        $totalOps = ($data.Datapoints | Measure-Object -Property Sum -Sum).Sum
        Write-Host ""
        Write-Host "Total Operations: $totalOps" -ForegroundColor Green
        Write-Host ""
        Write-Host "[OK] Data is being written to FSx!" -ForegroundColor Green
    } else {
        Write-Host "[WAIT] No write operations detected yet" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "This is normal if:" -ForegroundColor Gray
        Write-Host "  - Instance is still launching (first 5-10 min)" -ForegroundColor Gray
        Write-Host "  - Download phase is in progress (data not uploaded yet)" -ForegroundColor Gray
        Write-Host "  - CloudWatch metrics haven't updated (5-min delay)" -ForegroundColor Gray
    }
} else {
    Write-Host "Could not retrieve metrics" -ForegroundColor Red
}

Write-Host ""
Write-Host "Checking data written (last 30 minutes)..." -ForegroundColor Yellow
Write-Host ""

# Get bytes written metric
$writeBytes = aws cloudwatch get-metric-statistics `
    --namespace AWS/FSx `
    --metric-name DataWriteBytes `
    --dimensions Name=FileSystemId,Value=$FsxFileSystemId `
    --start-time $startTime `
    --end-time $endTime `
    --period 300 `
    --statistics Sum `
    --region $Region `
    --output json 2>$null

if ($LASTEXITCODE -eq 0) {
    $data = $writeBytes | ConvertFrom-Json
    
    if ($data.Datapoints.Count -gt 0) {
        Write-Host "Data Written:" -ForegroundColor Green
        
        $sortedPoints = $data.Datapoints | Sort-Object Timestamp -Descending | Select-Object -First 6
        
        foreach ($point in $sortedPoints) {
            $time = ([DateTime]$point.Timestamp).ToLocalTime().ToString("HH:mm:ss")
            $mb = [math]::Round($point.Sum / 1MB, 2)
            Write-Host "  $time : $mb MB" -ForegroundColor White
        }
        
        $totalBytes = ($data.Datapoints | Measure-Object -Property Sum -Sum).Sum
        $totalMB = [math]::Round($totalBytes / 1MB, 2)
        $totalGB = [math]::Round($totalBytes / 1GB, 2)
        
        Write-Host ""
        if ($totalGB -gt 1) {
            Write-Host "Total Data Written: $totalGB GB" -ForegroundColor Green
        } else {
            Write-Host "Total Data Written: $totalMB MB" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To check again in a few minutes:" -ForegroundColor Yellow
Write-Host "  .\check_fsx_simple.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To check EC2 instance:" -ForegroundColor Yellow
Write-Host "  .\check_10gb_job.ps1" -ForegroundColor White
Write-Host ""
