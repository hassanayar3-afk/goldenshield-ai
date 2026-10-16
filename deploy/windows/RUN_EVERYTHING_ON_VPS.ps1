# GoldenShield — تشغيل كامل على VPS (مرة واحدة كمسؤول)
param(
    [string]$Root = "C:\GoldenShield_Binance",
    [string]$Branch = "cursor/win-remote-deploy-fix-2e26",
    [string]$EnvFile = ""
)
$ErrorActionPreference = "Continue"
if (-not (Test-Path $Root)) { New-Item -ItemType Directory -Force -Path $Root | Out-Null }
Set-Location $Root

Write-Host "=== RUN_EVERYTHING_ON_VPS Root=$Root ==="

if (Test-Path (Join-Path $Root ".git")) {
    git fetch origin $Branch 2>&1
    git checkout $Branch 2>&1
    git pull origin $Branch 2>&1
} else {
    Write-Warning "Clone repo first into $Root"
}

if ($EnvFile -and (Test-Path $EnvFile)) {
    Copy-Item $EnvFile (Join-Path $Root ".env") -Force
    Write-Host "ENV_COPIED from $EnvFile"
} elseif (Test-Path (Join-Path $Root "goldenshield.env")) {
    Copy-Item (Join-Path $Root "goldenshield.env") (Join-Path $Root ".env") -Force
    Write-Host "ENV_COPIED from goldenshield.env"
}

$py = & (Join-Path $Root "deploy\windows\Resolve-GsPython.ps1") -Root $Root
& $py -m pip install -r requirements.txt --quiet
& $py scripts\bootstrap_storage.py

& (Join-Path $Root "deploy\windows\GS_START_FULL_STACK.ps1") -Root $Root
Start-Sleep -Seconds 10

& (Join-Path $Root "deploy\windows\START_DISCORD_BRIDGE.ps1") -Root $Root

try {
    $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 20
    Write-Host ("HEALTH ok=" + $h.ok)
} catch {
    Write-Host "HEALTH_FAIL" $_.Exception.Message
}

Write-Host "=== DONE — open tunnel URL on phone ==="
