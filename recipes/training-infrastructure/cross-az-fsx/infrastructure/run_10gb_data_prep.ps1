# Run 10GB Data Preparation Job
# This script orchestrates the complete 10GB dataset preparation using EC2

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
Write-Host "10GB Dataset Preparation" -ForegroundColor Cyan
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
Write-Host "  Volume Size: 10GB" -ForegroundColor White
Write-Host "  Chromosomes: chr1, chr2" -ForegroundColor White
Write-Host "  Destination: phase_10gb" -ForegroundColor White
Write-Host ""

# Confirm before proceeding
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  1. Launch a c5.4xlarge EC2 instance (about 0.68 USD per hour)" -ForegroundColor White
Write-Host "  2. Download chr1 and chr2 from UCSC (about 10GB)" -ForegroundColor White
Write-Host "  3. Upload to FSx volume in $AvailabilityZone" -ForegroundColor White
Write-Host "  4. Validate data integrity" -ForegroundColor White
Write-Host "  5. Terminate the instance automatically" -ForegroundColor White
Write-Host ""
Write-Host "Estimated time: 30-60 minutes" -ForegroundColor Cyan
Write-Host "Estimated cost: about 0.34 - 0.68 USD" -ForegroundColor Cyan
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

$outputFile = "results_10gb_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"

Write-Host "Launching EC2 instance..." -ForegroundColor Yellow
Write-Host ""

# Start the job in the background so we can capture the instance ID
$scriptDir = $PSScriptRoot
$job = Start-Job -ScriptBlock {
    param($FsxFileSystemId, $S3ScriptsBucket, $Region, $AvailabilityZone, $outputFile, $scriptDir)
    
    Set-Location $scriptDir
    
    python prepare_dataset_on_ec2.py `
        --fsx-file-system-id $FsxFileSystemId `
        --fsx-mount-name /genomics `
        --volume-size 10GB `
        --chromosomes chr1 chr2 `
        --dest-subdir phase_10gb `
        --s3-scripts-bucket $S3ScriptsBucket `
        --region $Region `
        --availability-zone $AvailabilityZone `
        --monitor-interval 60 `
        --max-runtime-hours 2 `
        --output $outputFile
} -ArgumentList $FsxFileSystemId, $S3ScriptsBucket, $Region, $AvailabilityZone, $outputFile, $scriptDir

Write-Host "Job started, monitoring progress..." -ForegroundColor Green
Write-Host ""
Write-Host "The job will run for approximately 30-60 minutes." -ForegroundColor Gray
Write-Host "You can safely press Ctrl+C to exit - the job will continue running." -ForegroundColor Gray
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

# Get job results
$jobOutput = Receive-Job -Job $job
$jobExitCode = if ($job.State -eq 'Completed') { 0 } else { 1 }

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
    if (Test-Path $outputFile) {
        Write-Host "Results:" -ForegroundColor Yellow
        Get-Content $outputFile | ConvertFrom-Json | Format-List
    }
    
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Verify data on FSx volume" -ForegroundColor White
    Write-Host "  2. Check validation logs at: /mnt/fsx/phase_10gb/logs/" -ForegroundColor White
    Write-Host "  3. Proceed with 100GB dataset preparation" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Data Preparation Failed" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error messages above for details" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
