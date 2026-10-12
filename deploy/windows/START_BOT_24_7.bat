@echo off
setlocal EnableExtensions
title GoldenShield — START 24/7 (Bot + Terminal API)
color 0A

set "GS_ROOT=%~dp0"
if "%GS_ROOT:~-1%"=="\" set "GS_ROOT=%GS_ROOT:~0,-1%"
if not exist "%GS_ROOT%\main.py" set "GS_ROOT=C:\GoldenShield_Binance"

if exist "%GS_ROOT%\scripts\gs_common_env.cmd" call "%GS_ROOT%\scripts\gs_common_env.cmd"

echo.
echo ========================================================
echo   GoldenShield — تشغيل 24/7 (لا سكون + بوت + Mobile API)
echo   Root: %GS_ROOT%
echo ========================================================
echo.

if not exist "%GS_ROOT%\main.py" (
  echo [ERROR] main.py not found
  pause
  exit /b 1
)

cd /d "%GS_ROOT%"

echo [1/5] No-Sleep mandatory...
powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\deploy\windows\ENFORCE_NO_SLEEP.ps1" -RegisterTask
powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\deploy\windows\ENFORCE_NO_SLEEP.ps1"
start "GoldenShield NO-SLEEP" /MIN powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\deploy\windows\ENFORCE_NO_SLEEP.ps1" -Loop

echo [2/5] Clear stop flag...
if exist "%GS_ROOT%\storage\runtime\user_stopped.flag" del /f /q "%GS_ROOT%\storage\runtime\user_stopped.flag"
if exist "%GS_ROOT%\storage\runtime\bot_instance.lock" del /f /q "%GS_ROOT%\storage\runtime\bot_instance.lock"

echo [3/5] Stop old workers...
if exist "%GS_ROOT%\scripts\gs_kill_all.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\scripts\gs_kill_all.ps1"
)
timeout /t 2 /nobreak >nul

echo [4/5] Mobile API (Terminal)...
start "GoldenShield Mobile API" /D "%GS_ROOT%" cmd /c "set GOLDENSHIELD_OFFICIAL_ROOT=%GS_ROOT%&& python -m terminal_app.server"
timeout /t 2 /nobreak >nul

echo [5/5] Bot daemon (auto-restart main.py)...
start "GoldenShield DAEMON 24/7" /D "%GS_ROOT%" powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\gs_daemon.ps1"

echo.
echo   STARTED — Bot + API. Stop: deploy\windows\STOP_BOT_FULL.bat
echo   Panel: http://127.0.0.1:8790/
echo.
timeout /t 3 /nobreak >nul
endlocal
exit /b 0
