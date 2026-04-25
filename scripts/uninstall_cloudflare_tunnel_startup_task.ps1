$ErrorActionPreference = "Stop"

$TaskName = "ATS Parking Cloudflare Tunnel"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed startup task: $TaskName"
