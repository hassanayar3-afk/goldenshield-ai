<#
  Contabo — بوت + لوحة + نفق (بدون لابتوب). يستخدم GS_SKIP_RUNTIME_SYNC=true.
#>
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
$scriptDir = $PSScriptRoot
Set-Location $Root

$envFile = Join-Path $Root ".env"
$c = Get-Content $envFile -Raw -Encoding UTF8
foreach ($line in @("GS_SKIP_RUNTIME_SYNC=true", "GS_PANEL_REMOTE_SNAPSHOT_ONLY=false", "BOT_FORCE_ACTIVE=true", "PROXY_URL=")) {
    $k = ($line -split "=", 2)[0]
    $v = ($line -split "=", 2)[1]
    if ($c -match ('(?m)^' + [regex]::Escape($k) + '=')) {
        $c = [regex]::Replace($c, ('(?m)^' + [regex]::Escape($k) + '=.*'), $line, 1)
    } else { $c = $c.TrimEnd() + "`n$line`n" }
}
Set-Content $envFile $c -Encoding UTF8

Write-Host "=== GOLDENSHIELD_VPS_FULL_AUTO Root=$Root ===" -ForegroundColor Cyan
& (Join-Path $scriptDir "GOLDENSHIELD_LAPTOP_ONE_SHOT.ps1") -Root $Root -SkipSyncWindow -WaitHeartbeatSec 120
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& (Join-Path $scriptDir "GS_START_FULL_STACK.ps1") -Root $Root
Start-Sleep -Seconds 15

try {
    $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 30
    Write-Host "health ok=$($h.ok) snap_age=$($h.spinal.snapshot_age_sec) fresh=$($h.spinal.snapshot_fresh)" -ForegroundColor Green
} catch { Write-Warning $_.Exception.Message }
try {
    $pl = Invoke-RestMethod "http://127.0.0.1:8790/api/mobile/pair-link" -TimeoutSec 30
    Write-Host "PANEL LIVE: $($pl.panel_pair_url)" -ForegroundColor Green
} catch { Write-Warning $_ }
exit 0
