# تشغيل Mobile API + (اختياري) البوت Tri-Commander
$ErrorActionPreference = "Continue"
$Target = "C:\GoldenShield_Binance"
Set-Location $Target
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Target

Write-Host "Starting Mobile API on port from .env (default 8790)..."
Start-Process python -ArgumentList "-m", "terminal_app.server" -WorkingDirectory $Target -WindowStyle Normal

Start-Sleep -Seconds 2
Write-Host "Starting main bot (TRI_COMMANDER_MODE from .env)..."
Start-Process python -ArgumentList "main.py" -WorkingDirectory $Target -WindowStyle Normal

Write-Host "Stack launched. Open http://127.0.0.1:8790/ for control panel."
