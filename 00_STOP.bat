@echo off
chcp 65001 >nul
title Stop GoldenShield Binance Demo
echo Stopping GoldenShield python main.py ...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Done.
echo Binance Demo account stays on the exchange.
pause
