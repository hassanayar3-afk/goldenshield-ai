# GoldenShield — إعداد البوت على اللابتوب (venv + .env + اختبار Binance)
param(
    [string]$Root = "",
    [switch]$SkipTest
)
$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = if ($env:GOLDENSHIELD_OFFICIAL_ROOT) { $env:GOLDENSHIELD_OFFICIAL_ROOT } else { (Get-Location).Path }
}
Set-Location $Root
Write-Host "=== Setup-LaptopTradingBot Root=$Root ==="

$venvPy = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $sysPy = (Get-Command python -ErrorAction Stop).Source
    & $sysPy -m venv (Join-Path $Root "venv")
    $venvPy = Join-Path $Root "venv\Scripts\python.exe"
}
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r (Join-Path $Root "requirements.txt")

$envFile = Join-Path $Root ".env"
$tpl = Join-Path $Root "config\laptop.env.template"
if (-not (Test-Path $envFile) -and (Test-Path $tpl)) {
    Copy-Item $tpl $envFile
    Write-Host "CREATED .env from config/laptop.env.template — fill BINANCE_* and WIN_*"
}

. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath $envFile
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root

if (-not $SkipTest) {
    & $venvPy (Join-Path $Root "scripts\test_binance_connection.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Binance test failed — check BINANCE_API_KEY/SECRET and PROXY_URL (should be empty on laptop)"
        exit $LASTEXITCODE
    }
}
Write-Host "SETUP_OK — next: Start-LaptopTradingBot.ps1 and Sync-RuntimeToContabo.ps1"
exit 0
