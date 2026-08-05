@echo off
setlocal EnableExtensions
title GoldenShield STOP BOT
color 0C

set "GS_ROOT=C:\GoldenShield_Binance"
set "GS_TASK=GoldenShieldBotOfficial"
set "GS_KILL=%GS_ROOT%\scripts\_kill_gs_workers.ps1"

echo.
echo ========================================================
echo   GoldenShield AI ^| STOP BOT
echo   Stop worker and close live windows
echo ========================================================
echo.

if not exist "%GS_ROOT%\main.py" (
  echo [ERROR] Project not found: %GS_ROOT%
  pause
  exit /b 1
)

cd /d "%GS_ROOT%"

echo [1/3] Stop official tasks...
schtasks /End /TN "%GS_TASK%" /F >nul 2>&1
schtasks /End /TN "GoldenShieldLiveConsole" /F >nul 2>&1
schtasks /End /TN "GoldenShieldStatusWindow" /F >nul 2>&1
schtasks /Delete /TN "GoldenShieldStatusWindow" /F >nul 2>&1

echo [2/3] Stop worker processes...
if exist "%GS_KILL%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_KILL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot|BOT_WINDOW|00_LIVE_CONSOLE' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
)
timeout /t 2 /nobreak >nul

echo [3/3] Mark manual stop...
if not exist "%GS_ROOT%\storage\runtime" mkdir "%GS_ROOT%\storage\runtime" >nul 2>&1
(
  echo {
  echo   "reason": "STOP_BOT.bat",
  echo   "source": "user",
  echo   "stopped_at": "%DATE% %TIME%"
  echo }
) > "%GS_ROOT%\storage\runtime\user_stopped.flag"
if exist "%GS_ROOT%\storage\runtime\bot_instance.lock" del /f /q "%GS_ROOT%\storage\runtime\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1

echo.
echo --------------------------------------------------------
echo   Bot status: stopped
echo   Data kept: DB, reports, logs
echo   Start again with START_BOT.bat
echo --------------------------------------------------------
echo.
pause
endlocal
exit /b 0
