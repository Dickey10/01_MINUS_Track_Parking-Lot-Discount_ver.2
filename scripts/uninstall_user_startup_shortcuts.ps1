$ErrorActionPreference = "Stop"

$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$Files = @(
    (Join-Path $StartupDir "ATS Parking Discount App.cmd"),
    (Join-Path $StartupDir "ATS Parking Cloudflare Tunnel.cmd")
)

foreach ($File in $Files) {
    if (Test-Path $File) {
        Remove-Item -LiteralPath $File -Force
        Write-Host "Removed: $File"
    }
}
