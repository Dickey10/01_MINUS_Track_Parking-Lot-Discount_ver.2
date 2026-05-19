$ErrorActionPreference = "Stop"

param(
    [string]$ExpectedPublicUrl = ""
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TaskName = "ATS Parking Daily Publish Check"
$CheckScript = Join-Path $ProjectRoot "scripts\check_daily_publish.ps1"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$Arguments = @(
    "-NoProfile"
    "-ExecutionPolicy"
    "Bypass"
    "-File"
    "`"$CheckScript`""
)

if ($ExpectedPublicUrl) {
    $Arguments += @("-ExpectedPublicUrl", "`"$ExpectedPublicUrl`"")
}

$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument ($Arguments -join " ")
$Trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Checks the MINUS Parking web app and Cloudflare tunnel each day at 9:00 AM when the PC is on." -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Runs daily at 9:00 AM."
Write-Host "Log file: data/daily_publish_check.log"
if ($ExpectedPublicUrl) {
    Write-Host "Expected public URL: $ExpectedPublicUrl"
}
