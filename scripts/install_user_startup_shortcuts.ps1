$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$ServerCmd = Join-Path $StartupDir "ATS Parking Discount App.cmd"
$TunnelCmd = Join-Path $StartupDir "ATS Parking Cloudflare Tunnel.cmd"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$ServerScript = Join-Path $ProjectRoot "scripts\start_server.ps1"
$TunnelScript = Join-Path $ProjectRoot "scripts\start_cloudflare_tunnel.ps1"

New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null

Set-Content -LiteralPath $ServerCmd -Encoding ASCII -Value "@echo off`r`nstart `"ATS Parking Discount App`" /min `"$PowerShell`" -NoProfile -ExecutionPolicy Bypass -File `"$ServerScript`"`r`n"
Set-Content -LiteralPath $TunnelCmd -Encoding ASCII -Value "@echo off`r`nstart `"ATS Parking Cloudflare Tunnel`" /min `"$PowerShell`" -NoProfile -ExecutionPolicy Bypass -File `"$TunnelScript`"`r`n"

Write-Host "Installed user startup shortcuts:"
Write-Host "  $ServerCmd"
Write-Host "  $TunnelCmd"
Write-Host ""
Write-Host "They will run after Windows login."
