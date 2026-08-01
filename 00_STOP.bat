@echo off
chcp 65001 >nul
title Stop GoldenShield Binance Demo
cd /d "%~dp0"
echo إيقاف عمليات البوت...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if not exist "storage\runtime" mkdir "storage\runtime" >nul 2>&1
echo stopped> "storage\runtime\user_stopped.flag"
echo تم الإيقاف.
echo حساب Binance Demo يبقى على المنصة كما هو.
pause
