$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "data"
$LogPath = Join-Path $LogDir "cloudflared.log"
$EnvPath = Join-Path $ProjectRoot ".env"
$DefaultCloudflared = "C:\Users\HOME\Downloads\cloudflared\cloudflared.exe"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Get-EnvValue {
    param([string]$Name)
    if (-not (Test-Path $EnvPath)) {
        return ""
    }
    $line = Get-Content $EnvPath | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
    if (-not $line) {
        return ""
    }
    return ($line -replace "^$Name=", "").Trim()
}

$Cloudflared = $env:CLOUDFLARED_PATH
if (-not $Cloudflared) {
    $Cloudflared = $DefaultCloudflared
}
if (-not (Test-Path $Cloudflared)) {
    throw "cloudflared.exe not found. Expected: $Cloudflared"
}

$Token = $env:CLOUDFLARE_TUNNEL_TOKEN
if (-not $Token) {
    $Token = Get-EnvValue "CLOUDFLARE_TUNNEL_TOKEN"
}

Set-Location $ProjectRoot

$ErrorActionPreference = "Continue"
if ($Token) {
    "Starting named Cloudflare Tunnel at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Append
    $Command = "`"$Cloudflared`" tunnel run --token $Token >> `"$LogPath`" 2>&1"
    & cmd.exe /c $Command
} else {
    "Starting temporary Cloudflare Tunnel at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Append
    "No CLOUDFLARE_TUNNEL_TOKEN found. This URL changes each time." | Out-File -FilePath $LogPath -Append
    $Command = "`"$Cloudflared`" tunnel --url http://127.0.0.1:8000 >> `"$LogPath`" 2>&1"
    & cmd.exe /c $Command
}
