@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul 2>&1
title SAQR TRADING ENGINE v6.2.3 - LIVE BRIDGE
color 0B
set "SAQR_HOLD_CONSOLE=1"

echo ========================================================
echo       SAQR ENGINE v6.2.3 - TELEGRAM and BINANCE BRIDGE
echo ========================================================
echo   Folder: %CD%
echo.

if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"

if exist "saqr.env" (
  copy /Y "saqr.env" ".env" >nul
  echo [OK] saqr.env copied to .env
)

if not exist ".env" (
  echo [ERROR] .env missing. Put saqr.env in this folder.
  pause
  exit /b 1
)

echo [OK] Loading environment - Paper 5000 USD - api.binance.com
echo.

set "SAQR_EXE="
if exist "bin\saqr.exe" set "SAQR_EXE=bin\saqr.exe"
if not defined SAQR_EXE if exist "saqr.exe" set "SAQR_EXE=saqr.exe"
if not defined SAQR_EXE if exist "target\release\saqr.exe" set "SAQR_EXE=target\release\saqr.exe"

if not defined SAQR_EXE (
  echo [ERROR] saqr.exe not found. Expected bin\saqr.exe or target\release\saqr.exe
  pause
  exit /b 9009
)

echo [CHECK] "%SAQR_EXE%" --check
call "%SAQR_EXE%" --check
if errorlevel 1 (
  echo [ERROR] preflight failed - check Binance and Telegram keys in .env
  pause
  exit /b 1
)

echo [RUN] Engine in this window - Telegram control panel mode
echo [RUN] Open Telegram bot for signals every 3 sec
echo.
findstr /I /C:"SAQR_WEB_ENABLED=false" ".env" >nul 2>&1
if errorlevel 1 (
  echo [RUN] Dashboard http://127.0.0.1:8788
  rundll32 url.dll,FileProtocolHandler "http://127.0.0.1:8788"
)

call "%SAQR_EXE%"
set "EC=%ERRORLEVEL%"

echo.
echo ========================================================
echo   Engine stopped. Exit code: %EC%
echo ========================================================
pause
exit /b %EC%
