# Deploy Muninn to demo.tolvuhvislarinn.is (public sandbox)
$ErrorActionPreference = "Stop"
$RemoteHost = "notandi@100.79.10.104"
$Remote = "/opt/demo-tolvuhvisl"
$Root = Split-Path -Parent $PSScriptRoot
$App = Join-Path $Root "app"
$SmokeUrl = "https://demo.tolvuhvislarinn.is/login"

Write-Host "Deploying demo to ${RemoteHost}:${Remote} ..."
ssh $RemoteHost "sudo mkdir -p ${Remote}/scripts; sudo chown -R notandi:notandi ${Remote}"

scp "$App/app.py" "${RemoteHost}:${Remote}/app.py"
scp "$App/customer_email.py" "${RemoteHost}:${Remote}/customer_email.py"
scp "$App/requirements.txt" "${RemoteHost}:${Remote}/requirements.txt"
scp -r "$App/muninn" "${RemoteHost}:${Remote}/"
scp -r "$App/templates" "${RemoteHost}:${Remote}/"
scp -r "$App/static" "${RemoteHost}:${Remote}/"

$ScriptsDir = Join-Path $Root "scripts"
scp "$ScriptsDir/seed_demo_db.py" "${RemoteHost}:${Remote}/scripts/seed_demo_db.py"
scp "$ScriptsDir/reset_demo_db.sh" "${RemoteHost}:${Remote}/scripts/reset_demo_db.sh"

$SetupSh = Join-Path $PSScriptRoot "demo-setup.sh"
scp $SetupSh "${RemoteHost}:/tmp/demo-setup.sh"
ssh $RemoteHost "sed -i 's/\r$//' /tmp/demo-setup.sh; bash /tmp/demo-setup.sh"

Write-Host "Smoke check: $SmokeUrl"
Start-Sleep -Seconds 2
try {
    $resp = Invoke-WebRequest -Uri $SmokeUrl -UseBasicParsing -TimeoutSec 20
    Write-Host "HTTP $($resp.StatusCode) OK"
} catch {
    Write-Warning "Smoke check failed (DNS or cert may still be propagating): $_"
    Write-Host "Try: ssh ${RemoteHost} curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5004/login"
}
Write-Host "Done."
