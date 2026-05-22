# Deploy Muninn app/ to th.tolvuhvislarinn.is (pantanir-tolvuhvisl)
$ErrorActionPreference = "Stop"
$RemoteHost = "notandi@100.79.10.104"
$Remote = "/opt/pantanir-tolvuhvisl"
$Root = Split-Path -Parent $PSScriptRoot
$App = Join-Path $Root "app"

Write-Host "Deploying to ${RemoteHost}:${Remote} ..."
scp "$App/app.py" "${RemoteHost}:${Remote}/app.py"
scp "$App/customer_email.py" "${RemoteHost}:${Remote}/customer_email.py"
scp -r "$App/templates" "${RemoteHost}:${Remote}/"
scp -r "$App/static" "${RemoteHost}:${Remote}/"
if (Test-Path "$App/requirements.txt") {
    scp "$App/requirements.txt" "${RemoteHost}:${Remote}/requirements.txt"
}
ssh $RemoteHost "sudo systemctl restart pantanir-tolvuhvisl; systemctl is-active pantanir-tolvuhvisl"
Write-Host "Done."
