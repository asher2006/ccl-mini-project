#!/usr/bin/env pwsh
# deploy.ps1 - Deploys CloudDrop app code (backend + frontend dist) to EC2
# Reads the EC2 public IP dynamically from AWS CLI, so it works after stop/start.
# Run from the project root: .\deploy.ps1

$KEY = "C:\Users\Ulric\.ssh\clouddrop-key.pem"
$INSTANCE_ID = "i-041d9c437d77036dc"

$EC2_IP = aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].PublicIpAddress" --output text
if (-not $EC2_IP -or $EC2_IP -eq "None") {
  Write-Host "ERROR: EC2 instance has no public IP. Is it running? Use: .\manage-clouddrop.ps1 -Action start" -ForegroundColor Red
  exit 1
}
Write-Host "Deploying to $EC2_IP..." -ForegroundColor Cyan

# Copy backend files
& scp -o StrictHostKeyChecking=no -i $KEY `
  clouddrop/backend/main.py `
  clouddrop/backend/config.py `
  clouddrop/backend/database.py `
  clouddrop/backend/worker.py `
  clouddrop/backend/requirements.txt `
  "ec2-user@${EC2_IP}:/tmp/"

# Copy frontend dist (built index.html + assets)
& ssh -o StrictHostKeyChecking=no -i $KEY "ec2-user@$EC2_IP" "rm -rf /tmp/dist"
& scp -o StrictHostKeyChecking=no -i $KEY -r `
  clouddrop/frontend/dist `
  "ec2-user@${EC2_IP}:/tmp/"

# Move files on server, sync frontend, install deps, restart service
$remote = @"
sudo cp /tmp/main.py /tmp/config.py /tmp/database.py /tmp/worker.py /opt/clouddrop/backend/
sudo rm -rf /opt/clouddrop/frontend/dist
sudo cp -r /tmp/dist /opt/clouddrop/frontend/dist
sudo chown -R clouddrop:clouddrop /opt/clouddrop/
sudo pip3 install -r /tmp/requirements.txt -q
sudo systemctl restart clouddrop
sudo systemctl status clouddrop --no-pager -l | head -n 12
"@

& ssh -o StrictHostKeyChecking=no -i $KEY "ec2-user@$EC2_IP" $remote

Write-Host "`nDeploy complete! App at: http://$EC2_IP" -ForegroundColor Green
