# Check FSx Volume Data
# This script shows what data has been uploaded to the FSx volume

param(
    [Parameter(Mandatory=$false)]
    [string]$FsxFileSystemId = "fs-04b3f909e86004fc2",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2",
    
    [Parameter(Mandatory=$false)]
    [string]$DestSubdir = "phase_10gb"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FSx Volume Data Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get FSx information
Write-Host "Getting FSx information..." -ForegroundColor Yellow

$fsxInfo = aws fsx describe-file-systems `
    --file-system-ids $FsxFileSystemId `
    --region $Region `
    --output json 2>$null | ConvertFrom-Json

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to get FSx information" -ForegroundColor Red
    exit 1
}

$fs = $fsxInfo.FileSystems[0]

Write-Host "File System ID: $FsxFileSystemId" -ForegroundColor White
Write-Host "Storage Capacity: $($fs.StorageCapacity) GB" -ForegroundColor White
Write-Host "Lifecycle: $($fs.Lifecycle)" -ForegroundColor White
Write-Host ""

# Get SVM information
Write-Host "Getting Storage Virtual Machine information..." -ForegroundColor Yellow

$svmInfo = aws fsx describe-storage-virtual-machines `
    --filters "Name=file-system-id,Values=$FsxFileSystemId" `
    --region $Region `
    --output json 2>$null | ConvertFrom-Json

if ($LASTEXITCODE -eq 0 -and $svmInfo.StorageVirtualMachines.Count -gt 0) {
    $svm = $svmInfo.StorageVirtualMachines[0]
    $svmDns = $svm.Endpoints.Nfs.DNSName
    
    Write-Host "SVM ID: $($svm.StorageVirtualMachineId)" -ForegroundColor White
    Write-Host "SVM DNS: $svmDns" -ForegroundColor White
    Write-Host ""
}

# Get volume information
Write-Host "Getting volume information..." -ForegroundColor Yellow

$volumeInfo = aws fsx describe-volumes `
    --filters "Name=file-system-id,Values=$FsxFileSystemId" `
    --region $Region `
    --output json 2>$null | ConvertFrom-Json

if ($LASTEXITCODE -eq 0 -and $volumeInfo.Volumes.Count -gt 0) {
    foreach ($vol in $volumeInfo.Volumes) {
        Write-Host "Volume ID: $($vol.VolumeId)" -ForegroundColor White
        Write-Host "Volume Path: $($vol.OntapConfiguration.JunctionPath)" -ForegroundColor White
        Write-Host "Volume Size: $($vol.OntapConfiguration.SizeInMegabytes) MB" -ForegroundColor White
        
        # Get volume metrics
        $endTime = Get-Date
        $startTime = $endTime.AddMinutes(-30)
        
        $storageUsed = aws cloudwatch get-metric-statistics `
            --namespace AWS/FSx `
            --metric-name StorageUsed `
            --dimensions Name=VolumeId,Value=$($vol.VolumeId) `
            --start-time $startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
            --end-time $endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
            --period 300 `
            --statistics Average `
            --region $Region `
            --query "Datapoints[-1].Average" `
            --output text 2>$null
        
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrEmpty($storageUsed) -and $storageUsed -ne "None") {
            $storageUsedMB = [math]::Round($storageUsed / 1MB, 2)
            Write-Host "Storage Used: $storageUsedMB MB" -ForegroundColor Green
        } else {
            Write-Host "Storage Used: Metrics not available" -ForegroundColor Yellow
        }
        
        Write-Host ""
    }
}

# Check CloudWatch metrics for data transfer
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Recent Data Transfer Activity" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$endTime = Get-Date
$startTime = $endTime.AddMinutes(-30)

# Check for NFS operations
$nfsOps = aws cloudwatch get-metric-statistics `
    --namespace AWS/FSx `
    --metric-name DataWriteOperations `
    --dimensions Name=FileSystemId,Value=$FsxFileSystemId `
    --start-time $startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
    --end-time $endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
    --period 300 `
    --statistics Sum `
    --region $Region `
    --output json 2>$null | ConvertFrom-Json

if ($LASTEXITCODE -eq 0 -and $null -ne $nfsOps.Datapoints -and $nfsOps.Datapoints.Count -gt 0) {
    Write-Host "Write Operations (last 30 minutes):" -ForegroundColor Yellow
    
    $sortedDatapoints = $nfsOps.Datapoints | Sort-Object Timestamp -Descending | Select-Object -First 6
    
    foreach ($dp in $sortedDatapoints) {
        $timestamp = [DateTime]::Parse($dp.Timestamp).ToLocalTime().ToString("HH:mm:ss")
        Write-Host "  $timestamp : $([math]::Round($dp.Sum, 0)) operations" -ForegroundColor White
    }
    
    $totalOps = ($nfsOps.Datapoints | Measure-Object -Property Sum -Sum).Sum
    Write-Host ""
    Write-Host "Total Write Operations: $([math]::Round($totalOps, 0))" -ForegroundColor Green
    
    if ($totalOps -gt 0) {
        Write-Host "[OK] Data is being written to FSx!" -ForegroundColor Green
    } else {
        Write-Host "[WAIT] No write activity detected yet" -ForegroundColor Yellow
    }
} else {
    Write-Host "No write operation metrics available yet" -ForegroundColor Yellow
    Write-Host "This is normal for the first few minutes after launch" -ForegroundColor Gray
}

Write-Host ""

# Check for data throughput
$throughput = aws cloudwatch get-metric-statistics `
    --namespace AWS/FSx `
    --metric-name DataWriteBytes `
    --dimensions Name=FileSystemId,Value=$FsxFileSystemId `
    --start-time $startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
    --end-time $endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
    --period 300 `
    --statistics Sum `
    --region $Region `
    --output json 2>$null | ConvertFrom-Json

if ($LASTEXITCODE -eq 0 -and $null -ne $throughput.Datapoints -and $throughput.Datapoints.Count -gt 0) {
    Write-Host "Data Written (last 30 minutes):" -ForegroundColor Yellow
    
    $sortedDatapoints = $throughput.Datapoints | Sort-Object Timestamp -Descending | Select-Object -First 6
    
    foreach ($dp in $sortedDatapoints) {
        $timestamp = [DateTime]::Parse($dp.Timestamp).ToLocalTime().ToString("HH:mm:ss")
        $mb = [math]::Round($dp.Sum / 1MB, 2)
        Write-Host "  $timestamp : $mb MB" -ForegroundColor White
    }
    
    $totalBytes = ($throughput.Datapoints | Measure-Object -Property Sum -Sum).Sum
    $totalMB = [math]::Round($totalBytes / 1MB, 2)
    $totalGB = [math]::Round($totalBytes / 1GB, 2)
    
    Write-Host ""
    if ($totalGB -gt 1) {
        Write-Host "Total Data Written: $totalGB GB" -ForegroundColor Green
    } else {
        Write-Host "Total Data Written: $totalMB MB" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (($null -ne $totalOps -and $totalOps -gt 0) -or ($null -ne $totalBytes -and $totalBytes -gt 0)) {
    Write-Host "[OK] Data is actively being written to FSx" -ForegroundColor Green
    Write-Host ""
    Write-Host "The data preparation job is progressing normally." -ForegroundColor White
    Write-Host "Files are being uploaded to: $DestSubdir" -ForegroundColor White
} else {
    Write-Host "[WAIT] No data transfer detected yet" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This could mean:" -ForegroundColor White
    Write-Host "  1. The instance is still launching (first 5-10 minutes)" -ForegroundColor Gray
    Write-Host "  2. The download phase is still in progress" -ForegroundColor Gray
    Write-Host "  3. CloudWatch metrics haven't updated yet (5-minute delay)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Check the EC2 console output to see current progress:" -ForegroundColor Yellow
    Write-Host "  .\check_job_progress.ps1" -ForegroundColor White
}

Write-Host ""
Write-Host "To check again in a few minutes:" -ForegroundColor Yellow
Write-Host "  .\check_fsx_data.ps1" -ForegroundColor White
Write-Host ""
