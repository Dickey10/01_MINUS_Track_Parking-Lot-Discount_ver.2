$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\HOME\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$LogDir = Join-Path $ProjectRoot "data"
$LogPath = Join-Path $LogDir "server.log"
$OutLogPath = Join-Path $LogDir "server.out.log"
$ErrLogPath = Join-Path $LogDir "server.err.log"
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

try {
    Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2 | Out-Null
    "Server already healthy at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Append -Encoding utf8
    exit 0
} catch {
}

"Starting ATS Parking server at $(Get-Date -Format s)" | Out-File -FilePath $LogPath -Append -Encoding utf8
"Binding to http://$HostAddress`:$Port" | Out-File -FilePath $LogPath -Append -Encoding utf8

$Args = @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", $Port)
Start-Process -FilePath $Python -ArgumentList $Args -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $OutLogPath -RedirectStandardError $ErrLogPath
