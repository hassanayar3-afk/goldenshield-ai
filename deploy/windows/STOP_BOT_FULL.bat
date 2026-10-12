@echo off
setlocal EnableExtensions
title GoldenShield — STOP (Bot + API)
color 0C

set "GS_ROOT=%~dp0"
if "%GS_ROOT:~-1%"=="\" set "GS_ROOT=%GS_ROOT:~0,-1%"
if not exist "%GS_ROOT%\main.py" set "GS_ROOT=C:\GoldenShield_Binance"

if exist "%GS_ROOT%\scripts\gs_common_env.cmd" call "%GS_ROOT%\scripts\gs_common_env.cmd"

echo.
echo ========================================================
echo   GoldenShield — إيقاف البوت و Mobile API
echo ========================================================
echo.

cd /d "%GS_ROOT%"

echo [1/4] Scheduled bot tasks...
schtasks /End /TN "GoldenShieldBotOfficial" /F >nul 2>&1
schtasks /End /TN "GoldenShieldLiveConsole" /F >nul 2>&1

echo [2/4] Kill Python workers...
if exist "%GS_ROOT%\scripts\gs_kill_all.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\scripts\gs_kill_all.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|terminal_app\.server|gs_daemon|mobile_api' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
)
timeout /t 2 /nobreak >nul

echo [3/4] Stop flag (no new entries)...
if not exist "%GS_ROOT%\storage\runtime" mkdir "%GS_ROOT%\storage\runtime"
echo mobile-stop-full> "%GS_ROOT%\storage\runtime\user_stopped.flag"

echo [4/4] Optional: end No-Sleep loop window (power settings stay 0)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process powershell -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'NO-SLEEP' } | Stop-Process -Force -EA SilentlyContinue"

echo.
echo   STOPPED. Start again: START_BOT_24_7.bat
echo.
pause
endlocal
exit /b 0
