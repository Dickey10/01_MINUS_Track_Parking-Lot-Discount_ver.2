$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\HOME\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$LogDir = Join-Path $ProjectRoot "data"
$LogPath = Join-Path $LogDir "server.log"
$EnvPath = Join-Path $ProjectRoot ".env"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

function Get-EnvValue {
    param(
        [string]$Name,
        [string]$DefaultValue
    )
    if (-not (Test-Path $EnvPath)) {
        return $DefaultValue
    }
    $line = Get-Content $EnvPath | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
    if (-not $line) {
        return $DefaultValue
    }
    $value = ($line -replace "^$Name=", "").Trim()
    if (-not $value) {
        return $DefaultValue
    }
    return $value
}

$HostAddress = Get-EnvValue "APP_HOST" "127.0.0.1"
$Port = Get-EnvValue "APP_PORT" "8000"

"Starting ATS Parking server at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Append
"Binding to http://$HostAddress`:$Port" | Out-File -FilePath $LogPath -Append
$ErrorActionPreference = "Continue"
& $Python -m uvicorn app.main:app --host $HostAddress --port $Port >> $LogPath 2>&1
