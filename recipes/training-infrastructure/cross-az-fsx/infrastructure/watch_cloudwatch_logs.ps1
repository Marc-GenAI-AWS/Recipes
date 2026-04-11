# Watch CloudWatch Logs in Real-Time
# This script tails CloudWatch Logs for the data preparation job

param(
    [Parameter(Mandatory=$false)]
    [string]$LogGroupName = "/aws/ec2/data-prep",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2",
    
    [Parameter(Mandatory=$false)]
    [string]$LogStreamPrefix = ""
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CloudWatch Logs - Real-Time Monitoring" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Log Group: $LogGroupName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Check if log group exists
$logGroupExists = aws logs describe-log-groups `
    --log-group-name-prefix $LogGroupName `
    --region $Region `
    --query "logGroups[?logGroupName=='$LogGroupName'].logGroupName" `
    --output text 2>$null

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($logGroupExists)) {
    Write-Host "Log group not found: $LogGroupName" -ForegroundColor Red
    Write-Host ""
    Write-Host "The log group will be created when the EC2 instance starts logging." -ForegroundColor Yellow
    Write-Host "Please wait a few minutes and try again." -ForegroundColor Yellow
    exit 1
}

# Tail logs
Write-Host "Streaming logs..." -ForegroundColor Green
Write-Host ""

if ([string]::IsNullOrEmpty($LogStreamPrefix)) {
    # Tail all streams in the log group
    aws logs tail $LogGroupName --follow --region $Region --format short
} else {
    # Tail specific stream
    aws logs tail $LogGroupName --follow --region $Region --format short --log-stream-name-prefix $LogStreamPrefix
}
