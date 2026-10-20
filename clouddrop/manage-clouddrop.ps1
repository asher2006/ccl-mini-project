<#
.SYNOPSIS
  Helper script to Pause or Resume CloudDrop AWS resources to save money.
.USAGE
  .\manage-clouddrop.ps1 -Action status
  .\manage-clouddrop.ps1 -Action stop
  .\manage-clouddrop.ps1 -Action start
#>

param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("start", "stop", "status")]
  [string]$Action
)

$INSTANCE_ID = "i-041d9c437d77036dc"
$DB_ID = "clouddrop-db"

if ($Action -eq "status") {
  Write-Host "=== EC2 Status ===" -ForegroundColor Cyan
  aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].{State:State.Name,IP:PublicIpAddress,Type:InstanceType}" --output table
  
  Write-Host "`n=== RDS Status ===" -ForegroundColor Cyan
  aws rds describe-db-instances --db-instance-identifier $DB_ID --query "DBInstances[0].{Status:DBInstanceStatus,Endpoint:Endpoint.Address}" --output table
}
elseif ($Action -eq "stop") {
  Write-Host "Stopping EC2 instance ($INSTANCE_ID)..." -ForegroundColor Yellow
  aws ec2 stop-instances --instance-ids $INSTANCE_ID | Out-Null
  
  Write-Host "Stopping RDS instance ($DB_ID)..." -ForegroundColor Yellow
  aws rds stop-db-instance --db-instance-identifier $DB_ID 2>&1 | Out-Null
  
  Write-Host "Both EC2 and RDS have been commanded to STOP. Zero compute charges will accrue while stopped!" -ForegroundColor Green
}
elseif ($Action -eq "start") {
  Write-Host "Starting RDS instance ($DB_ID)..." -ForegroundColor Yellow
  aws rds start-db-instance --db-instance-identifier $DB_ID 2>&1 | Out-Null
  
  Write-Host "Starting EC2 instance ($INSTANCE_ID)..." -ForegroundColor Yellow
  aws ec2 start-instances --instance-ids $INSTANCE_ID | Out-Null
  
  Write-Host "Waiting a moment for new Public IP..."
  Start-Sleep -Seconds 10
  $NEW_IP = aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].PublicIpAddress" --output text
  Write-Host "Services starting up! New Web URL: http://$NEW_IP" -ForegroundColor Green
}
