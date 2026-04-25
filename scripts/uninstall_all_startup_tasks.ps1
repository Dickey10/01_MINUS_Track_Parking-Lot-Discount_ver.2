$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

& (Join-Path $ProjectRoot "scripts\uninstall_startup_task.ps1")
& (Join-Path $ProjectRoot "scripts\uninstall_cloudflare_tunnel_startup_task.ps1")

Write-Host ""
Write-Host "Removed both startup tasks."
