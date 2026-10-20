#!/usr/bin/env pwsh
# deploy.ps1 - Deploys CloudDrop app code (backend + frontend dist) to EC2
# Reads the EC2 public IP dynamically from AWS CLI, so it works after stop/start.
# Run from the project root: .\deploy.ps1

$KEY = "C:\Users\Ulric\.ssh\clouddrop-key.pem"
$INSTANCE_ID = "i-041d9c437d77036dc"
$BACKEND = "$PSScriptRoot\backend"
$FRONTEND_DIST = "$PSScriptRoot\frontend\dist"

$EC2_IP = aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].PublicIpAddress" --output text
if (-not $EC2_IP -or $EC2_IP -eq "None") {
  Write-Host "ERROR: EC2 instance has no public IP. Is it running? Use: .\manage-clouddrop.ps1 -Action start" -ForegroundColor Red
  exit 1
}
Write-Host "Deploying to $EC2_IP..." -ForegroundColor Cyan

# Copy backend files
& scp -o StrictHostKeyChecking=no -i $KEY `
  "$BACKEND/main.py" `
  "$BACKEND/config.py" `
  "$BACKEND/database.py" `
  "$BACKEND/worker.py" `
  "$BACKEND/requirements.txt" `
  "ec2-user@${EC2_IP}:/tmp/"

# Copy frontend dist (built index.html + assets)
& ssh -o StrictHostKeyChecking=no -i $KEY "ec2-user@$EC2_IP" "rm -rf /tmp/dist"
& scp -o StrictHostKeyChecking=no -i $KEY -r `
  "$FRONTEND_DIST" `
  "ec2-user@${EC2_IP}:/tmp/"

# Optional: upload cookies if a local export exists (clouddrop/backend/cookies.txt)
$COOKIES_LOCAL = "$PSScriptRoot\backend\cookies.txt"
if ((Test-Path $COOKIES_LOCAL) -and (Get-Item $COOKIES_LOCAL).Length -gt 0) {
  Write-Host "Uploading cookies.txt to server..." -ForegroundColor Yellow
  & scp -o StrictHostKeyChecking=no -i $KEY "$COOKIES_LOCAL" "ec2-user@${EC2_IP}:/tmp/cookies.txt"
} else {
  Write-Host "No local cookies.txt found (backend/cookies.txt) - YouTube/Instagram downloads may hit bot-checks." -ForegroundColor Yellow
}

# Move files on server, sync frontend, install deps, restart service
$remote = @"
sudo cp /tmp/main.py /tmp/config.py /tmp/database.py /tmp/worker.py /opt/clouddrop/backend/
sudo rm -rf /opt/clouddrop/frontend/dist
sudo cp -r /tmp/dist /opt/clouddrop/frontend/dist
if [ -f /tmp/cookies.txt ]; then sudo install -m 640 -o clouddrop -g clouddrop /tmp/cookies.txt /etc/clouddrop/cookies.txt; fi
sudo chown -R clouddrop:clouddrop /opt/clouddrop/
sudo /opt/clouddrop/venv/bin/pip install -q -r /tmp/requirements.txt
sudo /opt/clouddrop/venv/bin/pip install -q -U yt-dlp
sudo systemctl restart clouddrop
sudo systemctl status clouddrop --no-pager -l | head -n 12
"@

& ssh -o StrictHostKeyChecking=no -i $KEY "ec2-user@$EC2_IP" $remote

Write-Host "`nDeploy complete! App at: http://$EC2_IP" -ForegroundColor Green
