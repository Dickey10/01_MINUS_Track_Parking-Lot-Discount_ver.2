$ErrorActionPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TunnelLog = Join-Path $ProjectRoot "data\cloudflared.err.log"

Write-Host "Local app:"
Write-Host "  http://127.0.0.1:8000/"
Write-Host ""

if (Test-Path $TunnelLog) {
    $Url = Select-String -Path $TunnelLog -Pattern 'https://[-a-z0-9]+\.trycloudflare\.com' -AllMatches |
        ForEach-Object { $_.Matches.Value } |
        Select-Object -Last 1

    if ($Url) {
        Write-Host "Current temporary Cloudflare URL:"
        Write-Host "  $Url/"
        Write-Host ""
        Write-Host "Health check:"
        Write-Host "  $Url/api/health"
        exit 0
    }
}

Write-Host "No temporary Cloudflare URL found yet."
Write-Host "Run .\scripts\start_cloudflare_tunnel.ps1, wait a few seconds, then run this script again."
