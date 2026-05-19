$ErrorActionPreference = "Stop"

param(
    [string]$ExpectedPublicUrl = ""
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "data"
$DailyLogPath = Join-Path $LogDir "daily_publish_check.log"
$TunnelErrLogPath = Join-Path $LogDir "cloudflared.err.log"
$EnvPath = Join-Path $ProjectRoot ".env"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-CheckLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $line | Out-File -FilePath $DailyLogPath -Append -Encoding utf8
}

function Get-EnvValue {
    param(
        [string]$Name,
        [string]$DefaultValue = ""
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

function Send-Alert {
    param(
        [string]$Subject,
        [string]$Body
    )

    Write-CheckLog "ALERT: $Subject"
    Write-CheckLog $Body

    if (-not (Test-Path $PythonPath)) {
        Write-CheckLog "Alert email skipped because Python runtime was not found at $PythonPath"
        return
    }

    $alertScript = @"
import sys
from app.config import settings
from app.integrations.mailer import _send_message

subject = sys.argv[1]
body = sys.argv[2]
recipients = [item.strip() for item in settings.alert_email.split(',') if item.strip()]
if recipients:
    _send_message(subject, body, recipients)
"@

    try {
        Set-Location $ProjectRoot
        & $PythonPath -c $alertScript $Subject $Body | Out-Null
        Write-CheckLog "Alert email sent."
    } catch {
        Write-CheckLog "Alert email failed: $($_.Exception.Message)"
    }
}

function Wait-ForHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod $Url -TimeoutSec 5
            if ($response.status -eq "ok") {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Get-LatestQuickTunnelUrl {
    if (-not (Test-Path $TunnelErrLogPath)) {
        return ""
    }

    $match = Select-String -Path $TunnelErrLogPath -Pattern 'https://[-a-z0-9]+\.trycloudflare\.com' -AllMatches |
        ForEach-Object { $_.Matches.Value } |
        Select-Object -Last 1

    if ($match) {
        return $match.TrimEnd("/")
    }

    return ""
}

function Get-LatestTunnelErrors {
    if (-not (Test-Path $TunnelErrLogPath)) {
        return ""
    }

    $tail = Get-Content $TunnelErrLogPath -Tail 30
    $errors = $tail | Where-Object { $_ -match '\b(ERR|error|failed)\b' }
    return ($errors -join [Environment]::NewLine).Trim()
}

Set-Location $ProjectRoot

$Port = Get-EnvValue "APP_PORT" "8000"
$HealthUrl = "http://127.0.0.1:$Port/api/health"
$TunnelToken = Get-EnvValue "CLOUDFLARE_TUNNEL_TOKEN"

Write-CheckLog "Daily publish check started."

try {
    & (Join-Path $ProjectRoot "scripts\start_server.ps1")
} catch {
    $message = "Server start script failed: $($_.Exception.Message)"
    Send-Alert -Subject "[MINUS Parking] Server start failed" -Body $message
    throw
}

if (-not (Wait-ForHealth -Url $HealthUrl)) {
    $message = "The app did not become healthy at $HealthUrl within the timeout window."
    Send-Alert -Subject "[MINUS Parking] Local health check failed" -Body $message
    throw $message
}

Write-CheckLog "Local health check passed at $HealthUrl"

if (Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue) {
    Write-CheckLog "Existing cloudflared process detected. Reusing current tunnel session."
} else {
    try {
        & (Join-Path $ProjectRoot "scripts\start_cloudflare_tunnel.ps1")
    } catch {
        $message = "Tunnel start script failed: $($_.Exception.Message)"
        Send-Alert -Subject "[MINUS Parking] Tunnel start failed" -Body $message
        throw
    }
}

Start-Sleep -Seconds 10

$QuickTunnelUrl = Get-LatestQuickTunnelUrl
$TunnelErrors = Get-LatestTunnelErrors

if ($TunnelErrors) {
    Send-Alert -Subject "[MINUS Parking] Tunnel error detected" -Body $TunnelErrors
    throw "Cloudflare tunnel error detected."
}

if (-not $TunnelToken -and -not $QuickTunnelUrl) {
    $message = "No quick tunnel URL was found after restart. Check data/cloudflared.err.log."
    Send-Alert -Subject "[MINUS Parking] Missing quick tunnel URL" -Body $message
    throw $message
}

if ($ExpectedPublicUrl) {
    $NormalizedExpectedUrl = $ExpectedPublicUrl.TrimEnd("/")
    if ($QuickTunnelUrl -and $QuickTunnelUrl -ne $NormalizedExpectedUrl) {
        $message = @"
Current quick tunnel URL: $QuickTunnelUrl
Expected URL: $NormalizedExpectedUrl

Cloudflare quick tunnel addresses rotate whenever the tunnel restarts. A fixed public URL requires a named tunnel with CLOUDFLARE_TUNNEL_TOKEN configured in .env.
"@
        Send-Alert -Subject "[MINUS Parking] Public URL mismatch" -Body $message.Trim()
        throw "Public URL mismatch detected."
    }
}

if ($QuickTunnelUrl) {
    Write-CheckLog "Public quick tunnel URL: $QuickTunnelUrl"
}

if ($TunnelToken) {
    Write-CheckLog "Named Cloudflare tunnel token is configured."
}

Write-CheckLog "Daily publish check completed successfully."
