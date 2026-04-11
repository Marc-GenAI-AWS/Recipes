# Build and push FSx validation container to ECR

$ErrorActionPreference = "Stop"

# Configuration
$Region = "us-west-2"
$AccountId = (aws sts get-caller-identity --query Account --output text)
$RepositoryName = "fsx-validation"
$ImageTag = "latest"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building FSx Validation Container" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Account ID: $AccountId" -ForegroundColor White
Write-Host "Region: $Region" -ForegroundColor White
Write-Host "Repository: $RepositoryName" -ForegroundColor White
Write-Host ""

# Create ECR repository if it doesn't exist
Write-Host "Creating ECR repository (if needed)..." -ForegroundColor Yellow
try {
    aws ecr describe-repositories --repository-names $RepositoryName --region $Region 2>$null | Out-Null
    Write-Host "Repository already exists" -ForegroundColor Green
} catch {
    aws ecr create-repository --repository-name $RepositoryName --region $Region | Out-Null
    Write-Host "Repository created" -ForegroundColor Green
}

# Get ECR login
Write-Host "Logging in to ECR..." -ForegroundColor Yellow
$password = aws ecr get-login-password --region $Region
$password | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ECR login failed" -ForegroundColor Red
    exit 1
}
Write-Host "Logged in successfully" -ForegroundColor Green

# Build Docker image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t "${RepositoryName}:${ImageTag}" .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "Image built successfully" -ForegroundColor Green

# Tag image
Write-Host "Tagging image..." -ForegroundColor Yellow
docker tag "${RepositoryName}:${ImageTag}" "$AccountId.dkr.ecr.$Region.amazonaws.com/${RepositoryName}:${ImageTag}"

# Push to ECR
Write-Host "Pushing to ECR..." -ForegroundColor Yellow
docker push "$AccountId.dkr.ecr.$Region.amazonaws.com/${RepositoryName}:${ImageTag}"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker push failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Container pushed successfully!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Image URI: $AccountId.dkr.ecr.$Region.amazonaws.com/${RepositoryName}:${ImageTag}" -ForegroundColor White
Write-Host ""
Write-Host "You can now launch a training job with:" -ForegroundColor Yellow
Write-Host "  python ../launch_test_training_job.py \" -ForegroundColor White
Write-Host "    --job-name test-cross-az-validation \" -ForegroundColor White
Write-Host "    --fsx-file-system-id fs-04b3f909e86004fc2 \" -ForegroundColor White
Write-Host "    --data-subdir phase_10gb" -ForegroundColor White
Write-Host ""
