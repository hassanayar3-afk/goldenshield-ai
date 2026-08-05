@echo off
setlocal EnableExtensions
title GoldenShield BOT — LIVE (Binance)
color 0A

REM Core visible runner — prints live pulse in THIS CMD window every ~3-5s
call "%~dp0scripts\gs_common_env.cmd" 2>nul
if not defined GS_ROOT set "GS_ROOT=C:\GoldenShield_Binance"
cd /d "%GS_ROOT%"

set "PYTHONPATH=%GS_ROOT%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "GOLDENSHIELD_OFFICIAL_ROOT=%GS_ROOT%"
set "GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true"
set "GOLDENSHIELD_LOCK_FAIL_CLOSED=true"
set "BOT_FORCE_ACTIVE=true"
set "NO_SLEEP_MODE=true"
set "LOOP_INTERVAL_SECONDS=4"
set "TELEGRAM_LIVE_SIGNALS=true"
set "TELEGRAM_LIVE_SIGNALS_SECONDS=4"
set "TELEGRAM_LIVE_POSITIONS_SECONDS=3"
set "SSOT_SYNC_ENABLED=true"
set "ENTERPRISE_PIPELINE_ENABLED=true"
set "EXECUTION_BACKEND=binance"

if not exist "%GS_ROOT%\main.py" (
  echo [ERROR] main.py not found in %GS_ROOT%
  pause
  exit /b 1
)
if not exist "%GS_ROOT%\.env" (
  echo [ERROR] .env not found
  pause
  exit /b 1
)

if not exist "%GS_ROOT%\storage\logs" mkdir "%GS_ROOT%\storage\logs" >nul 2>&1
if not exist "%GS_ROOT%\storage\runtime" mkdir "%GS_ROOT%\storage\runtime" >nul 2>&1

echo.
echo ========================================================
echo   GoldenShield AI ^| VISIBLE BOT WINDOW
echo   Binance only ^| No-Sleep ^| Single Instance
echo   Live signals pulse every ~4 seconds
echo ========================================================
echo.

set "PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PYEXE%" set "PYEXE=py"
if not exist "%PYEXE%" set "PYEXE=python"

echo [BOOT] Python: %PYEXE%
echo [BOOT] Root:   %GS_ROOT%
echo [BOOT] Mode:   NO_SLEEP + TELEGRAM + SSoT
echo.

REM Loop: if main exits unexpectedly, restart after 2s (unless user_stopped.flag)
:loop
if exist "%GS_ROOT%\storage\runtime\user_stopped.flag" (
  echo [STOP] user_stopped.flag present — exiting core window.
  goto :eof
)

"%PYEXE%" -u main.py
set "EC=%ERRORLEVEL%"
echo.
echo [EXIT] main.py code=%EC% — restart in 2s unless stopped...
timeout /t 2 /nobreak >nul
goto loop
