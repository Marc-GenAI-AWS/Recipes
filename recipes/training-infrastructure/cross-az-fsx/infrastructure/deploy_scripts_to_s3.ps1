# Deploy Data Preparation Scripts to S3
# This script uploads the data preparation scripts to S3 for EC2 instances to use

param(
    [Parameter(Mandatory=$false)]
    [string]$BucketName = "fsx-validation-scripts-$((Get-Date).ToString('yyyyMMdd'))",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deploying Data Preparation Scripts to S3" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if AWS CLI is available
try {
    aws --version | Out-Null
} catch {
    Write-Host "ERROR: AWS CLI not found. Please install AWS CLI first." -ForegroundColor Red
    exit 1
}

# Check if bucket exists, create if not
Write-Host "Checking S3 bucket: $BucketName" -ForegroundColor Yellow
$bucketExists = aws s3 ls "s3://$BucketName" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating S3 bucket: $BucketName" -ForegroundColor Yellow
    aws s3 mb "s3://$BucketName" --region $Region
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create S3 bucket" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Bucket created successfully" -ForegroundColor Green
} else {
    Write-Host "Bucket already exists" -ForegroundColor Green
}

# Upload data preparation scripts
Write-Host ""
Write-Host "Uploading data preparation scripts..." -ForegroundColor Yellow

$scriptsPath = Join-Path $PSScriptRoot "..\validation\data_preparation"

if (-not (Test-Path $scriptsPath)) {
    Write-Host "ERROR: Scripts directory not found: $scriptsPath" -ForegroundColor Red
    exit 1
}

# Upload Python scripts
Write-Host "  Uploading Python scripts..." -ForegroundColor Gray
aws s3 sync $scriptsPath "s3://$BucketName/scripts/" `
    --exclude "*.pyc" `
    --exclude "__pycache__/*" `
    --exclude "*.log" `
    --exclude "test_*.py" `
    --exclude "*_SUMMARY.md" `
    --exclude "*_README.md" `
    --exclude "example_*.py" `
    --exclude "demo_*.py" `
    --region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upload scripts" -ForegroundColor Red
    exit 1
}

Write-Host "Scripts uploaded successfully" -ForegroundColor Green

# List uploaded files
Write-Host ""
Write-Host "Uploaded files:" -ForegroundColor Yellow
aws s3 ls "s3://$BucketName/scripts/" --recursive --region $Region

# Output bucket information
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "S3 Bucket: $BucketName" -ForegroundColor Green
Write-Host "Region: $Region" -ForegroundColor Green
Write-Host "Scripts Path: s3://$BucketName/scripts/" -ForegroundColor Green
Write-Host ""
Write-Host "Use this bucket name when running prepare_dataset_on_ec2.py:" -ForegroundColor Yellow
Write-Host "  --s3-scripts-bucket $BucketName/scripts" -ForegroundColor White
Write-Host ""

# Save bucket name to file for easy reference
$bucketInfoFile = Join-Path $PSScriptRoot "s3_bucket_info.txt"
$createdDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$content = "S3_BUCKET_NAME=$BucketName`nS3_BUCKET_REGION=$Region`nS3_SCRIPTS_PATH=s3://$BucketName/scripts/`nCREATED_DATE=$createdDate"
$content | Out-File -FilePath $bucketInfoFile -Encoding UTF8

Write-Host "Bucket information saved to: $bucketInfoFile" -ForegroundColor Gray
