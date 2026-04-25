$ErrorActionPreference = "Stop"

$TaskName = "ATS Parking Discount App"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed startup task: $TaskName"

