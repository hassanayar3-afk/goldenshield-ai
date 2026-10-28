# Fix storage/runtime permissions (heartbeat.json Access denied on some VPS)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
$dirs = @(
    (Join-Path $Root "storage\runtime"),
    (Join-Path $Root "storage\logs"),
    (Join-Path $Root "storage\db"),
    (Join-Path $Root "storage\reports"),
    (Join-Path $Root "storage\mobile"),
    (Join-Path $env:ProgramData "GoldenShield")
)
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    icacls $d /inheritance:e /grant:r "${env:USERNAME}:(OI)(CI)F" "SYSTEM:(OI)(CI)F" /T 2>$null | Out-Null
}
$db = Join-Path $Root "storage\db\goldenshield.db"
if (Test-Path $db) {
    attrib -R $db 2>$null | Out-Null
    icacls $db /grant:r "${env:USERNAME}:F" "SYSTEM:F" 2>$null | Out-Null
}
Write-Output "RUNTIME_ACL_OK"
