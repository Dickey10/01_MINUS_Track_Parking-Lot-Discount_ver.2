$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

& (Join-Path $ProjectRoot "scripts\install_startup_task.ps1")
& (Join-Path $ProjectRoot "scripts\install_cloudflare_tunnel_startup_task.ps1")

Write-Host ""
Write-Host "Installed both startup tasks."
Write-Host "App: http://127.0.0.1:8000"
Write-Host "Server log: data/server.log"
Write-Host "Tunnel log: data/cloudflared.log"
