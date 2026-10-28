# GoldenShield — إذا توقف Mobile API أو main.py يعيد تشغيل الستاك (مهمة مجدولة)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
if (-not (Test-Path (Join-Path $Root "main.py"))) { exit 1 }

function Test-GsHealth {
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 12
        return [bool]$h.ok
    } catch {
        return $false
    }
}

if (Test-GsHealth) {
    Write-Output "WATCHDOG_OK"
    exit 0
}

Write-Output "WATCHDOG_RESTART health=false"
$viaTask = Join-Path $Root "deploy\windows\GS_START_VIA_TASK.ps1"
if (Test-Path $viaTask) {
    & $viaTask -Root $Root
} else {
    & (Join-Path $Root "deploy\windows\GS_START_FULL_STACK.ps1") -Root $Root
}
exit 0
