# Deploy Muninn to pan.tolvuhvislarinn.is (14-day trial instance)
$ErrorActionPreference = "Stop"
$RemoteHost = "notandi@100.79.10.104"
$Remote = "/opt/pan-tolvuhvisl"
$Root = Split-Path -Parent $PSScriptRoot
$App = Join-Path $Root "app"
$SmokeUrl = "https://pan.tolvuhvislarinn.is/login"

Write-Host "Deploying trial to ${RemoteHost}:${Remote} ..."
ssh $RemoteHost "sudo mkdir -p ${Remote}; sudo chown notandi:notandi ${Remote}"

scp "$App/app.py" "${RemoteHost}:${Remote}/app.py"
scp "$App/customer_email.py" "${RemoteHost}:${Remote}/customer_email.py"
scp "$App/requirements.txt" "${RemoteHost}:${Remote}/requirements.txt"
scp -r "$App/muninn" "${RemoteHost}:${Remote}/"
scp -r "$App/templates" "${RemoteHost}:${Remote}/"
scp -r "$App/static" "${RemoteHost}:${Remote}/"

$SetupSh = Join-Path $PSScriptRoot "pan-trial-setup.sh"
scp $SetupSh "${RemoteHost}:/tmp/pan-trial-setup.sh"
ssh $RemoteHost "sed -i 's/\r$//' /tmp/pan-trial-setup.sh; bash /tmp/pan-trial-setup.sh"

Write-Host "Smoke check: $SmokeUrl"
Start-Sleep -Seconds 2
try {
    $resp = Invoke-WebRequest -Uri $SmokeUrl -UseBasicParsing -TimeoutSec 20
    Write-Host "HTTP $($resp.StatusCode) OK"
} catch {
    Write-Warning "Smoke check failed (DNS or cert may still be propagating): $_"
    Write-Host "Try: ssh ${RemoteHost} curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5003/login"
}
Write-Host "Done."
