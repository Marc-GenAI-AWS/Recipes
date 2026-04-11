#!/usr/bin/env pwsh
# Terminate old instance and relaunch 10GB data prep job with fixed configuration

param(
    [Parameter(Mandatory=$false)]
    [string]$OldInstanceId = "i-05fe66a7bcd77cdcc",
    
    [Parameter(Mandatory=$false)]
    [string]$FsxFileSystemId = "fs-04b3f909e86004fc2",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2",
    
    [Parameter(Mandatory=$false)]
    [string]$AvailabilityZone = "us-west-2a"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Relaunch 10GB Data Prep Job" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Terminate old instance
Write-Host "Step 1: Terminating old instance..." -ForegroundColor Yellow
Write-Host "  Instance ID: $OldInstanceId" -ForegroundColor Gray

$instanceState = aws ec2 describe-instances --instance-ids $OldInstanceId --query 'Reservations[0].Instances[0].State.Name' --output text 2>$null

if ($LASTEXITCODE -eq 0 -and $instanceState -ne "terminated" -and $instanceState -ne "terminating") {
    Write-Host "  Current state: $instanceState" -ForegroundColor Gray
    Write-Host "  Terminating..." -ForegroundColor Yellow
    
    aws ec2 terminate-instances --instance-ids $OldInstanceId | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Termination initiated" -ForegroundColor Green
    } else {
        Write-Host "  Failed to terminate instance" -ForegroundColor Red
        Write-Host "  You may need to terminate it manually from AWS Console" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Instance already terminated or not found" -ForegroundColor Gray
}

Write-Host ""

# Step 2: Get S3 bucket info
Write-Host "Step 2: Getting S3 bucket configuration..." -ForegroundColor Yellow

$bucketInfoFile = Join-Path $PSScriptRoot "s3_bucket_info.txt"
$S3ScriptsBucket = ""

if (Test-Path $bucketInfoFile) {
    $content = Get-Content $bucketInfoFile
    foreach ($line in $content) {
        if ($line -match "^S3_BUCKET_NAME=(.+)$") {
            $bucketName = $matches[1]
            $S3ScriptsBucket = "$bucketName/scripts"
            Write-Host "  Found S3 bucket: $S3ScriptsBucket" -ForegroundColor Green
            break
        }
    }
}

if ([string]::IsNullOrEmpty($S3ScriptsBucket)) {
    Write-Host "  S3 bucket not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run deploy_scripts_to_s3.ps1 first" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 3: Display configuration
Write-Host "Step 3: New instance configuration:" -ForegroundColor Yellow
Write-Host "  Instance Type: c6i.4xlarge (faster network)" -ForegroundColor White
Write-Host "  Network: Up to 12.5 Gbps (1,562 MB/s)" -ForegroundColor White
Write-Host "  RAM: 32 GB" -ForegroundColor White
Write-Host "  Detailed Monitoring: Enabled (1-minute metrics)" -ForegroundColor White
Write-Host "  FSx File System: $FsxFileSystemId" -ForegroundColor White
Write-Host "  S3 Scripts: $S3ScriptsBucket" -ForegroundColor White
Write-Host "  Region: $Region" -ForegroundColor White
Write-Host "  Availability Zone: $AvailabilityZone" -ForegroundColor White
Write-Host ""
Write-Host "Dataset Configuration:" -ForegroundColor Yellow
Write-Host "  Volume Size: 10GB" -ForegroundColor White
Write-Host "  Chromosomes: chr1, chr2" -ForegroundColor White
Write-Host "  Destination: phase_10gb" -ForegroundColor White
Write-Host ""

# Step 4: Cost estimate
Write-Host "Cost Estimate:" -ForegroundColor Yellow
Write-Host "  Instance: ~`$0.68/hour (c6i.4xlarge)" -ForegroundColor White
Write-Host "  Detailed Monitoring: ~`$2.10/month (~`$0.003/hour)" -ForegroundColor White
Write-Host "  Estimated runtime: 30-60 minutes" -ForegroundColor White
Write-Host "  Estimated total: `$0.34 - `$0.68" -ForegroundColor Cyan
Write-Host ""

# Step 5: Confirm
$confirmation = Read-Host "Launch new instance? (yes/no)"
if ($confirmation -ne "yes") {
    Write-Host "Cancelled by user" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Launching New Instance" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 6: Launch new instance
$outputFile = "results_10gb_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"

Write-Host "Starting data preparation job..." -ForegroundColor Yellow
Write-Host ""

python "$PSScriptRoot/prepare_dataset_on_ec2.py" --fsx-file-system-id $FsxFileSystemId --fsx-mount-name /genomics --volume-size 10GB --chromosomes chr1 chr2 --dest-subdir phase_10gb --s3-scripts-bucket $S3ScriptsBucket --region $Region --availability-zone $AvailabilityZone --monitor-interval 60 --max-runtime-hours 2 --output $outputFile

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Job Launched Successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    
    if (Test-Path $outputFile) {
        $results = Get-Content $outputFile | ConvertFrom-Json
        $newInstanceId = $results.instance_id
        
        Write-Host "New Instance ID: $newInstanceId" -ForegroundColor Green
        Write-Host ""
        Write-Host "Monitor progress with:" -ForegroundColor Yellow
        Write-Host "  .\infrastructure\monitor_instance.ps1 -InstanceId $newInstanceId" -ForegroundColor White
        Write-Host ""
        Write-Host "Or view in AWS Console:" -ForegroundColor Yellow
        Write-Host "  https://console.aws.amazon.com/ec2/v2/home?region=$Region#InstanceDetails:instanceId=$newInstanceId" -ForegroundColor Blue
        Write-Host ""
        Write-Host "CloudWatch Metrics:" -ForegroundColor Yellow
        Write-Host "  https://console.aws.amazon.com/cloudwatch/home?region=$Region#metricsV2:graph=~();query=~'*7bNamespace*3d*27AWS*2fEC2*27*2cMetricName*3d*27CPUUtilization*27*2cInstanceId*3d*27$newInstanceId*27*7d" -ForegroundColor Blue
    }
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Launch Failed" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error messages above for details" -ForegroundColor Yellow
    exit 1
}
