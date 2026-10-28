param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$Version = "2026.10.5"
$AssetName = "cloudflared-windows-amd64.exe"
$ExpectedSha256 = "db4e4c413612a0916f3e1679d3caaf376f94911952d163028fb726fb2e0516a9"
$DownloadUrl = "https://github.com/cloudflare/cloudflared/releases/download/$Version/$AssetName"
$Cloudflared = $env:CLOUDFLARED_PATH
if (-not $Cloudflared) {
    $Cloudflared = Join-Path $env:USERPROFILE "Downloads\cloudflared\cloudflared.exe"
}

$InstallDir = Split-Path -Parent $Cloudflared
$StagedPath = Join-Path $InstallDir "cloudflared-$Version.new.exe"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

if (-not (Test-Path $StagedPath)) {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $StagedPath -UseBasicParsing
}

$actualHash = (Get-FileHash -LiteralPath $StagedPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $ExpectedSha256) {
    Remove-Item -LiteralPath $StagedPath -Force -ErrorAction SilentlyContinue
    throw "SHA-256 check failed for the staged cloudflared executable."
}

$versionOutput = (& $StagedPath --version 2>&1 | Out-String)
if ($versionOutput -notmatch "version\s+$([regex]::Escape($Version))\b") {
    Remove-Item -LiteralPath $StagedPath -Force -ErrorAction SilentlyContinue
    throw "The staged executable did not report the expected version $Version."
}

if (-not $Apply) {
    Write-Host "Verified cloudflared $Version and staged it at:"
    Write-Host "  $StagedPath"
    Write-Host "After the temporary replica is healthy and the named connector is stopped, run:"
    Write-Host "  .\scripts\update_cloudflared.ps1 -Apply"
    exit 0
}

if (-not (Test-Path $Cloudflared)) {
    Move-Item -LiteralPath $StagedPath -Destination $Cloudflared
    Write-Host "Installed cloudflared $Version at $Cloudflared."
    exit 0
}

$running = Get-CimInstance Win32_Process -Filter "Name = 'cloudflared.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -and ([IO.Path]::GetFullPath($_.ExecutablePath) -eq [IO.Path]::GetFullPath($Cloudflared)) }
if ($running) {
    throw "The selected cloudflared process is still running. Stop its scheduled task and wait for the connector to disconnect before applying."
}

$backupPath = "$Cloudflared.$(Get-Date -Format 'yyyyMMdd-HHmmss').bak"
[System.IO.File]::Replace($StagedPath, $Cloudflared, $backupPath)
$installedVersion = (& $Cloudflared --version 2>&1 | Out-String)
if ($installedVersion -notmatch "version\s+$([regex]::Escape($Version))\b") {
    Copy-Item -LiteralPath $backupPath -Destination $Cloudflared -Force
    throw "Installed version check failed; restored the prior executable from $backupPath."
}

Write-Host "Installed cloudflared $Version."
Write-Host "Previous executable backup: $backupPath"
Write-Host "Start the named Tunnel and confirm it is Healthy in Cloudflare Zero Trust."
