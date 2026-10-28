param(
    [switch]$Quick
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "data"
$LogPath = Join-Path $LogDir "cloudflared.log"
$OutLogPath = Join-Path $LogDir "cloudflared.out.log"
$ErrLogPath = Join-Path $LogDir "cloudflared.err.log"
$TokenPath = Join-Path $ProjectRoot "secrets\cloudflared-token"
$MinimumVersion = [version]"2026.10.2"
$DefaultCloudflared = Join-Path $env:USERPROFILE "Downloads\cloudflared\cloudflared.exe"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Cloudflared = $env:CLOUDFLARED_PATH
if (-not $Cloudflared) {
    $Cloudflared = $DefaultCloudflared
}
if (-not (Test-Path $Cloudflared)) {
    throw "cloudflared.exe not found. Set CLOUDFLARED_PATH or install it at: $Cloudflared"
}

$versionOutput = (& $Cloudflared --version 2>&1 | Out-String)
if ($versionOutput -notmatch "version\s+(\d{4}\.\d+\.\d+)") {
    throw "Could not read cloudflared version from: $versionOutput"
}
$installedVersion = [version]$Matches[1]
if ($installedVersion -lt $MinimumVersion) {
    throw "cloudflared $installedVersion is below the required $MinimumVersion. Stage and verify the official update with scripts\update_cloudflared.ps1."
}

if (-not $Quick) {
    if (-not (Test-Path $TokenPath)) {
        throw "Named Tunnel token file is missing. Run scripts\migrate_cloudflare_tunnel_token.ps1 first."
    }
    if ((Get-Item -LiteralPath $TokenPath).Length -eq 0) {
        throw "Named Tunnel token file is empty."
    }
    $Args = @("tunnel", "--no-autoupdate", "run", "--token-file", "`"$TokenPath`"")
} else {
    $Args = @("tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8000")
}

function Rotate-LogIfLarge {
    param([string]$Path)
    if ((Test-Path $Path) -and (Get-Item -LiteralPath $Path).Length -ge 10MB) {
        Move-Item -LiteralPath $Path -Destination "$Path.1" -Force
    }
}

foreach ($path in @($LogPath, $OutLogPath, $ErrLogPath)) {
    Rotate-LogIfLarge -Path $path
}

Set-Location $ProjectRoot

if ($Quick) {
    "Starting temporary Cloudflare Quick Tunnel at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Append -Encoding utf8
    "Temporary tunnel URL changes when the connector restarts." | Out-File -FilePath $LogPath -Append -Encoding utf8
} else {
    "Starting named Cloudflare Tunnel at $(Get-Date -Format s) with cloudflared $installedVersion" | Out-File -FilePath $LogPath -Append -Encoding utf8
}

Start-Process -FilePath $Cloudflared -ArgumentList $Args -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $OutLogPath -RedirectStandardError $ErrLogPath
