# Run once on VPS (Admin) so Cursor Cloud Agent can SSH with public key only.
param(
    [Parameter(Mandatory = $true)][string]$PublicKeyLine,
    [string]$UserName = $env:USERNAME
)
$ErrorActionPreference = "Stop"
$sshDir = Join-Path $env:USERPROFILE ".ssh"
$auth = Join-Path $sshDir "authorized_keys"
New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
$key = $PublicKeyLine.Trim()
if (-not $key.StartsWith("ssh-")) {
    throw "PublicKeyLine must start with ssh-ed25519 or ssh-rsa"
}
$existing = @()
if (Test-Path $auth) { $existing = Get-Content $auth -ErrorAction SilentlyContinue }
if ($existing -notcontains $key) {
    Add-Content -Path $auth -Value $key -Encoding ascii
}
# OpenSSH on Windows permissions
icacls $sshDir /inheritance:r /grant:r "${UserName}:(F)" /T | Out-Null
icacls $auth /inheritance:r /grant:r "${UserName}:(F)" | Out-Null
Restart-Service sshd -ErrorAction SilentlyContinue
Write-Host "CLOUD_AGENT_SSH_OK user=$UserName auth=$auth"
