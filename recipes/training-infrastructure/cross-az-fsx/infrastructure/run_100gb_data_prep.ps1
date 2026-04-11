# Run 100GB Data Preparation Job with CloudWatch Logs
# This script orchestrates the complete 100GB dataset preparation using EC2

param(
    [Parameter(Mandatory=$false)]
    [string]$FsxFileSystemId = "fs-04b3f909e86004fc2",
    
    [Parameter(Mandatory=$false)]
    [string]$S3ScriptsBucket = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2",
    
    [Parameter(Mandatory=$false)]
    [string]$AvailabilityZone = "us-west-2a"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "100GB Dataset Preparation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if S3 bucket is provided
if ([string]::IsNullOrEmpty($S3ScriptsBucket)) {
    # Try to read from saved file
    $bucketInfoFile = Join-Path $PSScriptRoot "s3_bucket_info.txt"
    if (Test-Path $bucketInfoFile) {
        Write-Host "Reading S3 bucket info from: $bucketInfoFile" -ForegroundColor Gray
        $content = Get-Content $bucketInfoFile
        foreach ($line in $content) {
            if ($line -match "^S3_BUCKET_NAME=(.+)$") {
                $bucketName = $matches[1]
                $S3ScriptsBucket = "$bucketName/scripts"
                Write-Host "Using S3 bucket: $S3ScriptsBucket" -ForegroundColor Green
                break
            }
        }
    }
    
    if ([string]::IsNullOrEmpty($S3ScriptsBucket)) {
        Write-Host "ERROR: S3 scripts bucket not specified" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please either:" -ForegroundColor Yellow
        Write-Host "  1. Run deploy_scripts_to_s3.ps1 first, or" -ForegroundColor Yellow
        Write-Host "  2. Specify -S3ScriptsBucket parameter" -ForegroundColor Yellow
        exit 1
    }
}

# Check if Python is available
try {
    python --version | Out-Null
} catch {
    Write-Host "ERROR: Python not found. Please install Python 3.8+ first." -ForegroundColor Red
    exit 1
}

# Check if boto3 is installed
Write-Host "Checking Python dependencies..." -ForegroundColor Yellow
$boto3Check = python -c "import boto3; print('ok')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing boto3..." -ForegroundColor Yellow
    pip install boto3
}
Write-Host "Python dependencies OK" -ForegroundColor Green

# Configuration
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  FSx File System: $FsxFileSystemId" -ForegroundColor White
Write-Host "  S3 Scripts Bucket: $S3ScriptsBucket" -ForegroundColor White
Write-Host "  Region: $Region" -ForegroundColor White
Write-Host "  Availability Zone: $AvailabilityZone" -ForegroundColor White
Write-Host "  Volume Size: 100GB" -ForegroundColor White
Write-Host "  Chromosomes: chr1-chr10" -ForegroundColor White
Write-Host "  Destination: phase_100gb" -ForegroundColor White
Write-Host "  CloudWatch Logs: ENABLED" -ForegroundColor Green
Write-Host ""

# Confirm before proceeding
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  1. Launch a c5.4xlarge EC2 instance (~$0.68/hour)" -ForegroundColor White
Write-Host "  2. Download chr1-chr10 from UCSC (~100GB)" -ForegroundColor White
Write-Host "  3. Upload to FSx volume in $AvailabilityZone" -ForegroundColor White
Write-Host "  4. Validate data integrity" -ForegroundColor White
Write-Host "  5. Stream logs to CloudWatch for real-time monitoring" -ForegroundColor White
Write-Host "  6. Terminate the instance automatically" -ForegroundColor White
Write-Host ""
Write-Host "Estimated time: 3-5 hours" -ForegroundColor Cyan
Write-Host "Estimated cost: ~$2.04 - $3.40" -ForegroundColor Cyan
Write-Host ""

$confirmation = Read-Host "Proceed? (yes/no)"
if ($confirmation -ne "yes") {
    Write-Host "Cancelled by user" -ForegroundColor Yellow
    exit 0
}

# Run the data preparation
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Data Preparation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$outputFile = "results_100gb_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"

# Start the Python orchestrator and capture the instance ID
Write-Host "Launching EC2 instance..." -ForegroundColor Yellow
Write-Host ""

# Start the job in the background
$job = Start-Job -ScriptBlock {
    param($FsxFileSystemId, $S3ScriptsBucket, $Region, $AvailabilityZone, $outputFile)
    
    python prepare_dataset_on_ec2.py `
        --fsx-file-system-id $FsxFileSystemId `
        --fsx-mount-name /genomics `
        --volume-size 100GB `
        --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 `
        --dest-subdir phase_100gb `
        --s3-scripts-bucket $S3ScriptsBucket `
        --region $Region `
        --availability-zone $AvailabilityZone `
        --monitor-interval 60 `
        --max-runtime-hours 6 `
        --enable-cloudwatch-logs `
        --output $outputFile
} -ArgumentList $FsxFileSystemId, $S3ScriptsBucket, $Region, $AvailabilityZone, $outputFile

Write-Host "Job started, waiting for instance to launch..." -ForegroundColor Green
Write-Host ""

# Wait for the instance to launch and CloudWatch Logs to be available
Write-Host "Waiting for CloudWatch Logs to become available (60 seconds)..." -ForegroundColor Yellow
Write-Host "The instance needs time to launch and configure the CloudWatch agent." -ForegroundColor Gray
Write-Host ""

Start-Sleep -Seconds 60

# Check if log group exists
Write-Host "Checking for CloudWatch Logs..." -ForegroundColor Yellow
$logGroupExists = $false
$maxRetries = 5
$retryCount = 0

while (-not $logGroupExists -and $retryCount -lt $maxRetries) {
    $logGroupCheck = aws logs describe-log-groups `
        --log-group-name-prefix "/aws/ec2/data-prep" `
        --region $Region `
        --query "logGroups[?logGroupName=='/aws/ec2/data-prep'].logGroupName" `
        --output text 2>$null
    
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrEmpty($logGroupCheck)) {
        $logGroupExists = $true
        Write-Host "✓ CloudWatch Logs available!" -ForegroundColor Green
    } else {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "  Waiting for logs... (attempt $retryCount/$maxRetries)" -ForegroundColor Gray
            Start-Sleep -Seconds 15
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Real-Time Log Streaming" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($logGroupExists) {
    Write-Host "Streaming CloudWatch Logs in real-time..." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop watching logs (job will continue running)" -ForegroundColor Gray
    Write-Host ""
    
    # Start streaming logs in the foreground
    # This will run until the user presses Ctrl+C or the logs stop
    try {
        aws logs tail /aws/ec2/data-prep --follow --region $Region --format short
    } catch {
        Write-Host ""
        Write-Host "Log streaming stopped." -ForegroundColor Yellow
    }
} else {
    Write-Host "CloudWatch Logs not available yet." -ForegroundColor Yellow
    Write-Host "The instance may still be launching or the CloudWatch agent may be starting." -ForegroundColor Gray
    Write-Host ""
    Write-Host "You can manually watch logs with:" -ForegroundColor Yellow
    Write-Host "  aws logs tail /aws/ec2/data-prep --follow --region $Region" -ForegroundColor White
    Write-Host ""
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Checking Job Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if the job is still running
if ($job.State -eq 'Running') {
    Write-Host "The data preparation job is still running in the background." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  1. Wait for completion (recommended)" -ForegroundColor White
    Write-Host "  2. Exit and check results later" -ForegroundColor White
    Write-Host ""
    
    $waitChoice = Read-Host "Wait for job completion? (yes/no)"
    
    if ($waitChoice -eq "yes") {
        Write-Host ""
        Write-Host "Waiting for job to complete..." -ForegroundColor Yellow
        Write-Host "This may take several hours. You can safely press Ctrl+C to exit." -ForegroundColor Gray
        Write-Host ""
        
        # Monitor the job
        $lastStatus = ""
        while ($job.State -eq 'Running') {
            $elapsed = [math]::Round((New-TimeSpan -Start $job.PSBeginTime).TotalMinutes, 1)
            $currentStatus = "Job running... (elapsed: $elapsed minutes)"
            if ($currentStatus -ne $lastStatus) {
                Write-Host $currentStatus -ForegroundColor Gray
                $lastStatus = $currentStatus
            }
            Start-Sleep -Seconds 30
        }
    } else {
        Write-Host ""
        Write-Host "Job is running in the background." -ForegroundColor Green
        Write-Host "Results will be saved to: $outputFile" -ForegroundColor White
        Write-Host ""
        Write-Host "To check status later:" -ForegroundColor Yellow
        Write-Host "  aws logs tail /aws/ec2/data-prep --region $Region" -ForegroundColor White
        Write-Host ""
        exit 0
    }
}

# Get job results
$jobOutput = Receive-Job -Job $job
$jobExitCode = $job.State -eq 'Completed' ? 0 : 1

# Display output
Write-Host ""
Write-Host $jobOutput

if ($jobExitCode -eq 0 -and (Test-Path $outputFile)) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Data Preparation Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Results saved to: $outputFile" -ForegroundColor Green
    Write-Host ""
    
    # Display results
    Write-Host "Results:" -ForegroundColor Yellow
    Get-Content $outputFile | ConvertFrom-Json | Format-List
    
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Verify data on FSx volume" -ForegroundColor White
    Write-Host "  2. Check validation logs at: /mnt/fsx/phase_100gb/logs/" -ForegroundColor White
    Write-Host "  3. Review CloudWatch Logs for detailed execution trace" -ForegroundColor White
    Write-Host "  4. Proceed with 500GB dataset preparation" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Data Preparation Failed" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error messages above for details" -ForegroundColor Yellow
    Write-Host "Review CloudWatch Logs for more information:" -ForegroundColor Yellow
    Write-Host "  aws logs tail /aws/ec2/data-prep --region $Region" -ForegroundColor White
    Write-Host ""
    exit 1
}
