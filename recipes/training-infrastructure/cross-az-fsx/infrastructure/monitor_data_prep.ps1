# Monitor Data Preparation Progress
# This script monitors the EC2 instance and shows real-time progress

param(
    [Parameter(Mandatory=$true)]
    [string]$InstanceId,
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-west-2",
    
    [Parameter(Mandatory=$false)]
    [int]$RefreshInterval = 30
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Monitoring Data Preparation Progress" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Instance ID: $InstanceId" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Refresh Interval: $RefreshInterval seconds" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Gray
Write-Host ""

$lastOutputLength = 0

while ($true) {
    try {
        # Get instance status
        $instanceInfo = aws ec2 describe-instances `
            --instance-ids $InstanceId `
            --region $Region `
            --query 'Reservations[0].Instances[0].[State.Name,LaunchTime]' `
            --output text 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            $state, $launchTime = $instanceInfo -split "`t"
            
            # Calculate elapsed time
            $launched = [DateTime]::Parse($launchTime)
            $elapsed = (Get-Date) - $launched
            $elapsedStr = "{0:D2}:{1:D2}:{2:D2}" -f $elapsed.Hours, $elapsed.Minutes, $elapsed.Seconds
            
            Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] Instance State: $state | Elapsed: $elapsedStr" -ForegroundColor Cyan
            
            # Check if terminated
            if ($state -eq "terminated" -or $state -eq "shutting-down") {
                Write-Host ""
                Write-Host "Instance is $state - job complete or failed" -ForegroundColor Yellow
                break
            }
        }
        
        # Get console output
        $output = aws ec2 get-console-output `
            --instance-id $InstanceId `
            --region $Region `
            --output text 2>$null
        
        if ($LASTEXITCODE -eq 0 -and $output) {
            # Only show new output
            $currentLength = $output.Length
            if ($currentLength -gt $lastOutputLength) {
                $newOutput = $output.Substring($lastOutputLength)
                
                # Parse and highlight important lines
                $lines = $newOutput -split "`n"
                foreach ($line in $lines) {
                    if ($line -match "ERROR|Failed|failed") {
                        Write-Host $line -ForegroundColor Red
                    }
                    elseif ($line -match "SUCCESS|Success|completed|✓") {
                        Write-Host $line -ForegroundColor Green
                    }
                    elseif ($line -match "Downloading|Uploading|Calculating|Validating") {
                        Write-Host $line -ForegroundColor Yellow
                    }
                    elseif ($line -match "====") {
                        Write-Host $line -ForegroundColor Cyan
                    }
                    else {
                        Write-Host $line
                    }
                }
                
                $lastOutputLength = $currentLength
            }
        }
        
        Write-Host ""
        Start-Sleep -Seconds $RefreshInterval
        
    } catch {
        Write-Host "Error monitoring instance: $_" -ForegroundColor Red
        Start-Sleep -Seconds $RefreshInterval
    }
}

Write-Host ""
Write-Host "Monitoring complete" -ForegroundColor Green
