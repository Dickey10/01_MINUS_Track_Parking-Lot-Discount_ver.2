$Host.UI.RawUI.WindowTitle = "MINUS Track Setup"
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Clear-Host
Write-Host "============================================"
Write-Host "  MINUS Track Parking Discount Auto Setup"
Write-Host "============================================"
Write-Host ""

$ProjectRoot = $PSScriptRoot
$EnvPath = Join-Path $ProjectRoot ".env"
if (Test-Path $EnvPath) {
    throw "An existing .env file was found. Setup stops to protect current credentials and settings. Back it up and edit it manually if you intend to change them."
}

function New-RandomHex {
    param([int]$ByteCount)
    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return (-join ($bytes | ForEach-Object { $_.ToString("x2") }))
}

# Step 1: Check Python
Write-Host "[1/6] Checking Python..."
try {
    $pyver = python --version 2>&1
    Write-Host "  OK: $pyver"
} catch {
    Write-Host "  ERROR: Python not found. Install from python.org first."
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 2: ATS and initial administrator credentials
Write-Host ""
Write-Host "[2/6] Enter ATS login credentials (https://a00992.pweb.kr)"
Write-Host ""
$atsId = Read-Host "  ATS ID"
$atsPw = Read-Host "  ATS Password"
$adminUsername = Read-Host "  Initial app administrator ID"
$adminPassword = New-RandomHex -ByteCount 24

if (-not $atsId -or -not $atsPw -or -not $adminUsername) {
    throw "ATS credentials and administrator ID are required."
}

# Step 3: Create .env file with a unique signing key and initial password
Write-Host ""
Write-Host "[3/6] Creating .env file..."
$secretKey = New-RandomHex -ByteCount 48
$envLines = @(
    "ATS_ID=$atsId",
    "ATS_PW=$atsPw",
    "ATS_URL=https://a00992.pweb.kr",
    "SESSION_PATH=data/storage_state.json",
    "SCREENSHOT_DIR=data/screenshots",
    "DATABASE_PATH=data/parking_app.db",
    "APP_HOST=127.0.0.1",
    "APP_PORT=8000",
    "GSHEET_ID=",
    "GSHEET_CREDS_PATH=data/gsheet_creds.json",
    "SMTP_HOST=smtp.gmail.com",
    "SMTP_PORT=587",
    "SMTP_USER=",
    "SMTP_PASSWORD=",
    "ALERT_EMAIL=",
    "API_KEY=",
    "SECRET_KEY=$secretKey",
    "ADMIN_USERNAME=$adminUsername",
    "ADMIN_PASSWORD=$adminPassword",
    "CORS_ORIGINS="
)
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($EnvPath, [string[]]$envLines, $utf8NoBom)
Write-Host "  OK: .env created"

# Step 4: Create folders
Write-Host ""
Write-Host "[4/6] Creating data folders..."
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "data\screenshots") | Out-Null
Write-Host "  OK: folders created"

# Step 5: Install packages
Write-Host ""
Write-Host "[5/6] Installing Python packages (this may take 2-3 minutes)..."
python -m pip install -r (Join-Path $ProjectRoot "requirements.txt") --quiet
python -m playwright install chromium
Write-Host "  OK: packages installed"

# Step 6: ATS login session
Write-Host ""
Write-Host "[6/6] ATS Login Session"
Write-Host ""
Write-Host "  IMPORTANT:"
Write-Host "  1. A Chrome browser will open automatically"
Write-Host "  2. Log in to ATS in that browser"
Write-Host "  3. After login, come back here and press Enter"
Write-Host ""
Read-Host "  Press Enter to open the browser"

Push-Location $ProjectRoot
try {
    python scripts/init_session.py
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Setup Complete!"
Write-Host "============================================"
Write-Host ""
Write-Host "  Initial app administrator:"
Write-Host "    ID: $adminUsername"
Write-Host "    Temporary password: $adminPassword"
Write-Host "  Save it securely and change it after the first login."
Write-Host ""
Write-Host "  To start the server, run this command:"
Write-Host ""
Write-Host "    python -m uvicorn app.main:app --reload"
Write-Host ""
Read-Host "Press Enter to exit"
