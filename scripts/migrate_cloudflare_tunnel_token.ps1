$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SecretDir = Join-Path $ProjectRoot "secrets"
$TokenPath = Join-Path $SecretDir "cloudflared-token"
$EnvPath = Join-Path $ProjectRoot ".env"

if (Test-Path $TokenPath) {
    throw "Tunnel token file already exists. Remove or rotate it deliberately before migrating another token."
}

$token = ""
$tokenFromEnv = $false
if (Test-Path $EnvPath) {
    $match = Get-Content -LiteralPath $EnvPath | Where-Object { $_ -match "^CLOUDFLARE_TUNNEL_TOKEN=" } | Select-Object -First 1
    if ($match) {
        $token = ($match -replace "^CLOUDFLARE_TUNNEL_TOKEN=", "").Trim()
        $tokenFromEnv = [bool]$token
    }
}

if (-not $token) {
    $secureToken = Read-Host "Paste the named Tunnel token" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    try {
        $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Tunnel token was empty; no files were changed."
}

New-Item -ItemType Directory -Force -Path $SecretDir | Out-Null
[System.IO.File]::WriteAllText($TokenPath, $token, (New-Object System.Text.UTF8Encoding $false))

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$acl = New-Object System.Security.AccessControl.FileSecurity
$acl.SetOwner([System.Security.Principal.NTAccount]$identity)
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $identity,
    [System.Security.AccessControl.FileSystemRights]::Read -bor [System.Security.AccessControl.FileSystemRights]::Write,
    [System.Security.AccessControl.AccessControlType]::Allow
)
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $TokenPath -AclObject $acl

if ($tokenFromEnv) {
    $remaining = Get-Content -LiteralPath $EnvPath | Where-Object { $_ -notmatch "^CLOUDFLARE_TUNNEL_TOKEN=" }
    [System.IO.File]::WriteAllLines($EnvPath, [string[]]$remaining, (New-Object System.Text.UTF8Encoding $false))
}

$token = $null
Write-Host "Tunnel token saved to secrets/cloudflared-token with a current-user-only file ACL."
if ($tokenFromEnv) {
    Write-Host "Removed CLOUDFLARE_TUNNEL_TOKEN from .env."
}
