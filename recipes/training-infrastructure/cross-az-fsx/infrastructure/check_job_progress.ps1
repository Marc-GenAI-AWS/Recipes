# Check Data Preparation Job Progress
# This script helps you monitor what's happening on the EC2 instance and FSx volume

param(
    [Parameter(Mandatory=$false)]
    [string]$InstanceId = "",
    
    [Parameter(Mandatory=$false)]
    [string]$FsxFileSystemId = "fs-04b3f909e86004fc2",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Data Preparation Progress Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# If no instance ID provided, try to find running data-prep instances
if ([string]::IsNullOrEmpty($InstanceId)) {
    Write-Host "Looking for running data-prep instances..." -ForegroundColor Yellow
    
    $instances = aws ec2 describe-instances `
        --region $Region `
        --filters "Name=tag:Name,Values=data-prep-*" "Name=instance-state-name,Values=running" `
        --query "Reservations[*].Instances[*].[InstanceId,Tags[?Key=='Name'].Value|[0],LaunchTime]" `
        --output text
    
    if ([string]::IsNullOrEmpty($instances)) {
        Write-Host "No running data-prep instances found." -ForegroundColor Red
        Write-Host ""
        Write-Host "Please specify the instance ID:" -ForegroundColor Yellow
        Write-Host "  .\check_job_progress.ps1 -InstanceId i-xxxxx" -ForegroundColor White
        exit 1
    }
    
    Write-Host "Found running instances:" -ForegroundColor Green
    Write-Host $instances
    Write-Host ""
    
    # Use the first instance
    $InstanceId = ($instances -split "`t")[0]
    Write-Host "Using instance: $InstanceId" -ForegroundColor Green
}

Write-Host ""
Write-Host "Instance ID: $InstanceId" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""

# 1. Check instance state
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "1. Instance State" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$instanceState = aws ec2 describe-instances `
    --instance-ids $InstanceId `
    --region $Region `
    --query "Reservations[0].Instances[0].[State.Name,LaunchTime,InstanceType,PrivateIpAddress]" `
    --output text

if ($LASTEXITCODE -eq 0) {
    $stateInfo = $instanceState -split "`t"
    Write-Host "  State: $($stateInfo[0])" -ForegroundColor Green
    Write-Host "  Launch Time: $($stateInfo[1])" -ForegroundColor White
    Write-Host "  Instance Type: $($stateInfo[2])" -ForegroundColor White
    Write-Host "  Private IP: $($stateInfo[3])" -ForegroundColor White
    
    # Calculate elapsed time
    $launchTime = [DateTime]::Parse($stateInfo[1])
    $elapsed = (Get-Date) - $launchTime
    Write-Host "  Elapsed Time: $([math]::Floor($elapsed.TotalMinutes)) minutes" -ForegroundColor White
} else {
    Write-Host "  Failed to get instance state" -ForegroundColor Red
}

Write-Host ""

# 2. Check console output for progress
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "2. Recent Console Output (Last 50 Lines)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$consoleOutput = aws ec2 get-console-output `
    --instance-id $InstanceId `
    --region $Region `
    --output text 2>$null

if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrEmpty($consoleOutput)) {
    # Get last 50 lines and highlight important messages
    $lines = $consoleOutput -split "`n" | Select-Object -Last 50
    
    foreach ($line in $lines) {
        if ($line -match "ERROR|Failed|failed") {
            Write-Host $line -ForegroundColor Red
        } elseif ($line -match "✓|SUCCESS|Successfully|completed") {
            Write-Host $line -ForegroundColor Green
        } elseif ($line -match "Downloading|Uploading|Validating|Progress") {
            Write-Host $line -ForegroundColor Yellow
        } elseif ($line -match "====") {
            Write-Host $line -ForegroundColor Cyan
        } else {
            Write-Host $line -ForegroundColor White
        }
    }
} else {
    Write-Host "  Console output not available yet (instance may still be launching)" -ForegroundColor Yellow
}

Write-Host ""

# 3. Check FSx volume usage
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "3. FSx Volume Storage Usage" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$fsxInfo = aws fsx describe-file-systems `
    --file-system-ids $FsxFileSystemId `
    --region $Region `
    --query "FileSystems[0].[StorageCapacity,LustreConfiguration.DataRepositoryConfiguration.ImportedFileChunkSize]" `
    --output json 2>$null | ConvertFrom-Json

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Storage Capacity: $($fsxInfo[0]) GB" -ForegroundColor White
    
    # Get CloudWatch metrics for storage used
    $endTime = Get-Date
    $startTime = $endTime.AddMinutes(-30)
    
    $storageUsed = aws cloudwatch get-metric-statistics `
        --namespace AWS/FSx `
        --metric-name StorageUsed `
        --dimensions Name=FileSystemId,Value=$FsxFileSystemId `
        --start-time $startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
        --end-time $endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") `
        --period 300 `
        --statistics Average `
        --region $Region `
        --query "Datapoints[-1].Average" `
        --output text 2>$null
    
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrEmpty($storageUsed) -and $storageUsed -ne "None") {
        $storageUsedGB = [math]::Round($storageUsed / 1GB, 2)
        $percentUsed = [math]::Round(($storageUsedGB / $fsxInfo[0]) * 100, 2)
        Write-Host "  Storage Used: $storageUsedGB GB - $percentUsed percent" -ForegroundColor Green
    } else {
        Write-Host "  Storage Used: Metrics not available yet" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Failed to get FSx information" -ForegroundColor Red
}

Write-Host ""

# 4. Check for specific progress indicators
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "4. Progress Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not [string]::IsNullOrEmpty($consoleOutput)) {
    $phases = @{
        "System Setup" = $consoleOutput -match "Installing dependencies"
        "CloudWatch Logs" = $consoleOutput -match "CloudWatch Logs agent started"
        "FSx Mount" = $consoleOutput -match "FSx volume mounted successfully"
        "Scripts Downloaded" = $consoleOutput -match "Scripts downloaded successfully"
        "Download Started" = $consoleOutput -match "Downloading hg38 Chromosome Data"
        "Download Complete" = $consoleOutput -match "Download completed"
        "Checksums Calculated" = $consoleOutput -match "Checksums calculated"
        "Upload Started" = $consoleOutput -match "Uploading Data to FSx"
        "Upload Complete" = $consoleOutput -match "Upload completed"
        "Validation Started" = $consoleOutput -match "Validating Data Integrity"
        "Validation Complete" = $consoleOutput -match "Validation completed"
        "Job Complete" = $consoleOutput -match "Data Preparation Completed Successfully"
    }
    
    foreach ($phase in $phases.GetEnumerator() | Sort-Object Name) {
        if ($phase.Value) {
            $status = "[X]"
            $color = "Green"
        } else {
            $status = "[ ]"
            $color = "Gray"
        }
        Write-Host "  $status $($phase.Key)" -ForegroundColor $color
    }
    
    # Estimate current phase
    Write-Host ""
    if ($phases["Job Complete"]) {
        Write-Host "  Current Status: JOB COMPLETE!" -ForegroundColor Green
    } elseif ($phases["Validation Started"]) {
        Write-Host "  Current Status: Validating data integrity..." -ForegroundColor Yellow
    } elseif ($phases["Upload Started"]) {
        Write-Host "  Current Status: Uploading to FSx..." -ForegroundColor Yellow
    } elseif ($phases["Download Started"]) {
        Write-Host "  Current Status: Downloading chromosome data..." -ForegroundColor Yellow
    } elseif ($phases["FSx Mount"]) {
        Write-Host "  Current Status: Setting up..." -ForegroundColor Yellow
    } else {
        Write-Host "  Current Status: Instance launching..." -ForegroundColor Yellow
    }
} else {
    Write-Host "  Console output not available yet" -ForegroundColor Yellow
}

Write-Host ""

# 5. Provide next steps
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "5. Monitoring Options" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To continuously monitor console output:" -ForegroundColor Yellow
Write-Host "  .\monitor_data_prep.ps1 -InstanceId $InstanceId" -ForegroundColor White
Write-Host ""
Write-Host "To watch CloudWatch Logs (if enabled):" -ForegroundColor Yellow
Write-Host "  aws logs tail /aws/ec2/data-prep --follow --region $Region" -ForegroundColor White
Write-Host ""
Write-Host "To check progress again:" -ForegroundColor Yellow
Write-Host "  .\check_job_progress.ps1 -InstanceId $InstanceId" -ForegroundColor White
Write-Host ""
Write-Host "To SSH into the instance (if needed):" -ForegroundColor Yellow
Write-Host "  # First, get the private IP from above" -ForegroundColor Gray
Write-Host "  ssh ec2-user@PRIVATE-IP" -ForegroundColor White
Write-Host ""
