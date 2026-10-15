# Start or verify GoldenShield Mobile API on port 8790 (service preferred, else process).
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
if (-not (Test-Path (Join-Path $Root "main.py"))) { exit 1 }
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root

function Test-GsMobileHealth {
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 10
        return [bool]$h.ok
    } catch {
        return $false
    }
}

if (Test-GsMobileHealth) {
    Write-Output "MOBILE_API_OK"
    exit 0
}

$svc = Get-Service -Name "GoldenShieldMobileApi" -ErrorAction SilentlyContinue
if ($svc) {
    try {
        if ($svc.Status -ne "Running") {
            Start-Service -Name "GoldenShieldMobileApi" -ErrorAction Stop
        }
        Start-Sleep -Seconds 3
        if (Test-GsMobileHealth) {
            Write-Output "MOBILE_API_SERVICE_STARTED"
            exit 0
        }
    } catch {
        Write-Warning ("MOBILE_API_SERVICE_FAIL " + $_.Exception.Message)
    }
}

$listen = @(Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue).Count
if ($listen -gt 0 -and -not (Test-GsMobileHealth)) {
    Write-Warning "PORT_8790_BUSY_BUT_UNHEALTHY"
}

$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
Start-Process -FilePath $py -ArgumentList @("-m", "terminal_app.server") `
    -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep -Seconds 4
if (Test-GsMobileHealth) {
    Write-Output "MOBILE_API_PROCESS_STARTED"
    exit 0
}
Write-Output "MOBILE_API_START_FAILED"
exit 1
