# Simple script to check 10GB data prep job status
# Uses direct AWS CLI commands to avoid PowerShell syntax issues

param(
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "10GB Data Prep Job Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Find running data-prep instances
Write-Host "Looking for running EC2 instances..." -ForegroundColor Yellow
Write-Host ""

$instances = aws ec2 describe-instances `
    --region $Region `
    --filters "Name=tag:Name,Values=data-prep-*" "Name=instance-state-name,Values=running,stopped,terminated" `
    --query "Reservations[*].Instances[*].[InstanceId,State.Name,LaunchTime,Tags[?Key=='Name'].Value|[0]]" `
    --output text

if ([string]::IsNullOrEmpty($instances)) {
    Write-Host "No data-prep instances found" -ForegroundColor Red
    Write-Host ""
    Write-Host "The instance may have already terminated." -ForegroundColor Yellow
    Write-Host "Check for results file: results_10gb_*.json" -ForegroundColor Yellow
    exit 0
}

Write-Host "Found instances:" -ForegroundColor Green
Write-Host $instances
Write-Host ""

# Get the first instance ID
$instanceId = ($instances -split "`t")[0]
$instanceState = ($instances -split "`t")[1]

Write-Host "Instance ID: $instanceId" -ForegroundColor White
Write-Host "State: $instanceState" -ForegroundColor White
Write-Host ""

if ($instanceState -eq "terminated") {
    Write-Host "Instance has terminated - job is complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Check results file: results_10gb_*.json" -ForegroundColor Yellow
    exit 0
}

# Get console output
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Recent Console Output" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$output = aws ec2 get-console-output --instance-id $instanceId --region $Region --output text 2>$null

if ([string]::IsNullOrEmpty($output)) {
    Write-Host "Console output not available yet" -ForegroundColor Yellow
    Write-Host "Instance may still be launching..." -ForegroundColor Gray
} else {
    # Show last 30 lines
    $lines = $output -split "`n" | Select-Object -Last 30
    foreach ($line in $lines) {
        Write-Host $line
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Quick Commands" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Get full console output:" -ForegroundColor Yellow
Write-Host "  aws ec2 get-console-output --instance-id $instanceId --region $Region --output text" -ForegroundColor White
Write-Host ""
Write-Host "Check instance state:" -ForegroundColor Yellow
Write-Host "  aws ec2 describe-instances --instance-ids $instanceId --region $Region --query 'Reservations[0].Instances[0].State.Name'" -ForegroundColor White
Write-Host ""
Write-Host "Run this script again:" -ForegroundColor Yellow
Write-Host "  .\check_10gb_job.ps1" -ForegroundColor White
Write-Host ""
