# Run 10GB Data Preparation Job (Auto-confirm version)
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
Write-Host "10GB Dataset Preparation (Auto)" -ForegroundColor Cyan
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
        exit 1
    }
}

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

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Data Preparation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$outputFile = "results_10gb_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"

Write-Host "Launching EC2 instance..." -ForegroundColor Yellow
Write-Host ""

# Run directly (not in background job)
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

if ($LASTEXITCODE -eq 0 -and (Test-Path $outputFile)) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Data Preparation Completed Successfully" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Results saved to: $outputFile" -ForegroundColor Green
    Write-Host ""
    
    # Display results
    $results = Get-Content $outputFile | ConvertFrom-Json
    Write-Host "Instance ID: $($results.instance_id)" -ForegroundColor White
    Write-Host "Status: $($results.status)" -ForegroundColor White
    Write-Host "Runtime: $($results.runtime_minutes) minutes" -ForegroundColor White
    
    if ($results.fsx_data_uploaded) {
        Write-Host "Data uploaded to FSx: $($results.fsx_data_uploaded)" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Data Preparation Failed" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error messages above for details" -ForegroundColor Yellow
    exit 1
}
