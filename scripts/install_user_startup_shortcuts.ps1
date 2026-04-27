$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$ServerVbs = Join-Path $StartupDir "ATS Parking Discount App.vbs"
$TunnelVbs = Join-Path $StartupDir "ATS Parking Cloudflare Tunnel.vbs"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$ServerScript = Join-Path $ProjectRoot "scripts\start_server.ps1"
$TunnelScript = Join-Path $ProjectRoot "scripts\start_cloudflare_tunnel.ps1"

New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null

$ServerContent = @"
Set WshShell = CreateObject("WScript.Shell")
cmd = """" & "$PowerShell" & """ -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & "$ServerScript" & """"
WshShell.Run cmd, 0, False
"@

$TunnelContent = @"
Set WshShell = CreateObject("WScript.Shell")
cmd = """" & "$PowerShell" & """ -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & "$TunnelScript" & """"
WshShell.Run cmd, 0, False
"@

Set-Content -LiteralPath $ServerVbs -Encoding ASCII -Value $ServerContent
Set-Content -LiteralPath $TunnelVbs -Encoding ASCII -Value $TunnelContent

Remove-Item -LiteralPath (Join-Path $StartupDir "ATS Parking Discount App.cmd") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $StartupDir "ATS Parking Cloudflare Tunnel.cmd") -Force -ErrorAction SilentlyContinue

Write-Host "Installed user startup shortcuts:"
Write-Host "  $ServerVbs"
Write-Host "  $TunnelVbs"
Write-Host ""
Write-Host "They will run after Windows login."
