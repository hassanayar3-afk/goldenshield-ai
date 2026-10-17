# One-shot: إعداد + اختبار + بوت + مزامنة Contabo (شغّل على اللابتوب كمسؤول)
param(
    [string]$Root = "",
    [switch]$SkipSyncLoop
)
$ErrorActionPreference = "Continue"
if (-not $Root) {
    $Root = if ($env:GOLDENSHIELD_OFFICIAL_ROOT) { $env:GOLDENSHIELD_OFFICIAL_ROOT } else { (Get-Location).Path }
}
Set-Location $Root

& (Join-Path $PSScriptRoot "Setup-LaptopTradingBot.ps1") -Root $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& (Join-Path $PSScriptRoot "Start-LaptopTradingBot.ps1") -Root $Root -UseDaemon
Start-Sleep -Seconds 12

$hb = Join-Path $Root "storage\runtime\heartbeat.json"
$snap = Join-Path $Root "storage\runtime\binance_snapshot.json"
if (-not (Test-Path $hb)) {
    Write-Warning "heartbeat.json missing — check storage\logs\gs_daemon.log"
}

& (Join-Path $Root "venv\Scripts\python.exe") (Join-Path $Root "scripts\sync_runtime_to_contabo.py")
if ($LASTEXITCODE -ne 0) {
    Write-Warning "First sync failed — enable SSH (22) on Contabo or use WinRM from Cloud Agent"
}

if (-not $SkipSyncLoop) {
    Write-Host "Starting continuous sync (15s) — keep this window open"
    & (Join-Path $PSScriptRoot "Sync-RuntimeToContabo.ps1") -Root $Root
}
