<#
.SYNOPSIS
  Contabo — لوحة + Mobile API فقط (البوت على اللابتوب + مزامنة runtime).
#>
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
$scriptDir = $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "main.py"))) {
    throw "GoldenShield not found at $Root"
}
Write-Host "=== GoldenShield CONTABO PANEL ONE-SHOT ===" -ForegroundColor Cyan

& (Join-Path $scriptDir "Start-PanelOnlyContabo.ps1") -Root $Root
Start-Sleep -Seconds 8

try {
    $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 25
    Write-Host "health ok=$($h.ok)" -ForegroundColor Green
} catch {
    Write-Warning $_.Exception.Message
}
try {
    $pl = Invoke-RestMethod "http://127.0.0.1:8790/api/mobile/pair-link" -TimeoutSec 25
    Write-Host "PANEL: $($pl.panel_pair_url)" -ForegroundColor Green
    $pl.panel_pair_url | Set-Clipboard -ErrorAction SilentlyContinue
    Write-Host "(URL copied to clipboard if available)"
} catch {
    Write-Warning "pair-link failed"
}
Write-Host "Ensure laptop runs GOLDENSHIELD_LAPTOP_ONE_SHOT.ps1 with sync window open."
exit 0
