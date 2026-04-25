$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
docker compose up -d --build
Write-Host "Docker app is running at http://127.0.0.1:8000"

