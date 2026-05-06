$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FallbackPython = "C:\Users\HOME\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

Set-Location $ProjectRoot

if (-not (Test-Path $VenvPython)) {
    if (-not (Test-Path $FallbackPython)) {
        throw "No Python found. Expected fallback runtime at $FallbackPython"
    }
    & $FallbackPython -m venv ".venv"
}

& $VenvPython -m pip install -r requirements.txt
Write-Host "Runtime ready: $VenvPython"
