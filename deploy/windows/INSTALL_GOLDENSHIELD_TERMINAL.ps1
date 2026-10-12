# GoldenShield Terminal — تثبيت سريع بعد فك ZIP على Windows VPS
# شغّل PowerShell كمسؤول من مجلد المشروع المفكوك:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\deploy\windows\INSTALL_GOLDENSHIELD_TERMINAL.ps1

$ErrorActionPreference = "Stop"
$Target = "C:\GoldenShield_Binance"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $Here "..\..")

Write-Host "=== GoldenShield Terminal Install ==="
Write-Host "Source: $Root"
Write-Host "Target: $Target"

if (-not (Test-Path $Target)) {
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
}

# نسخ الملفات (استثناء .venv)
robocopy $Root $Target /MIR /XD .git .venv __pycache__ .pytest_cache dist /XF .env /R:1 /W:1 | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed $LASTEXITCODE" }

$envTemplate = Join-Path $Target ".env.template"
$envFile = Join-Path $Target ".env"
if (-not (Test-Path $envFile) -and (Test-Path $envTemplate)) {
    Copy-Item $envTemplate $envFile
    Write-Host "Created .env from .env.template — edit API keys before live."
}

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python not found on PATH" }

Set-Location $Target
& $py.Source -m pip install -r requirements.txt --upgrade --quiet

New-Item -ItemType Directory -Force -Path (Join-Path $Target "storage\runtime") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Target "storage\db") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Target "storage\logs") | Out-Null

Write-Host "=== Server launchers (24/7 + no-sleep) ==="
$launcherInstaller = Join-Path $Here "INSTALL_SERVER_LAUNCHERS.ps1"
if (Test-Path $launcherInstaller) {
    & $launcherInstaller
} else {
    Write-Warning "INSTALL_SERVER_LAUNCHERS.ps1 not found — skip shortcuts"
}

Write-Host "=== DONE ==="
Write-Host "1) Edit $envFile (Binance Demo keys, TELEGRAM optional)"
Write-Host "2) Start 24/7 (bot + API + no-sleep): $Target\START_BOT_24_7.bat"
Write-Host "   Stop: $Target\STOP_BOT_FULL.bat"
Write-Host "3) Or stack only: .\deploy\windows\START_TERMINAL_STACK.ps1"
Write-Host "4) Smoke: python scripts\smoke_terminal_api.py"
