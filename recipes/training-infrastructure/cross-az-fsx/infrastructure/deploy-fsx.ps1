# Deploy FSx infrastructure for cross-AZ validation

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "FSx Infrastructure Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if AWS credentials are configured
Write-Host "Checking AWS credentials..."
try {
    $accountId = aws sts get-caller-identity --query Account --output text
    if ($LASTEXITCODE -ne 0) { throw "AWS credentials not configured" }
} catch {
    Write-Host "ERROR: AWS credentials not configured" -ForegroundColor Red
    Write-Host "Please run: aws configure"
    exit 1
}

$region = "us-west-2"

Write-Host "Account ID: $accountId"
Write-Host "Region: $region"
Write-Host ""

# Bootstrap CDK if needed
Write-Host "Checking CDK bootstrap status..."
$bootstrapExists = aws cloudformation describe-stacks --stack-name CDKToolkit --region $region 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Bootstrapping CDK..."
    npx cdk bootstrap "aws://$accountId/$region"
} else {
    Write-Host "CDK already bootstrapped"
}
Write-Host ""

# Deploy stacks in order
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying Network Stack..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
npx cdk deploy CrossAzFsxSageMakerNetwork --require-approval never
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying IAM Stack..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
npx cdk deploy CrossAzFsxSageMakerIam --require-approval never
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying FSx Stack..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "NOTE: FSx deployment takes 20-30 minutes" -ForegroundColor Yellow
npx cdk deploy CrossAzFsxSageMakerFsx --require-approval never
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Get FSx information
Write-Host "Retrieving FSx connection information..."
$svmId = aws cloudformation describe-stacks `
  --stack-name CrossAzFsxSageMakerFsx `
  --query 'Stacks[0].Outputs[?OutputKey==`StorageVirtualMachineId`].OutputValue' `
  --output text

if ($svmId) {
    Write-Host "Storage Virtual Machine ID: $svmId"
    Write-Host ""
    Write-Host "Waiting for SVM to be available..."
    aws fsx wait storage-virtual-machine-available --storage-virtual-machine-ids $svmId
    
    $svmDns = aws fsx describe-storage-virtual-machines `
      --storage-virtual-machine-ids $svmId `
      --query 'StorageVirtualMachines[0].Endpoints.Nfs.DNSName' `
      --output text
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "FSx Connection Information" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "SVM DNS Name: $svmDns"
    Write-Host "Mount Path: /genomics"
    Write-Host ""
    Write-Host "Mount Command:"
    Write-Host "  sudo mount -t nfs ${svmDns}:/genomics /mnt/fsx"
    Write-Host ""
}

Write-Host "Deployment complete! FSx is ready for use." -ForegroundColor Green
