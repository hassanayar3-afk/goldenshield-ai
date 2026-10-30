@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SAQR TRADING ENGINE v6.2.3 - LIVE BRIDGE
color 0B
cd /d "%~dp0"
set "SAQR_HOLD_CONSOLE=1"

echo ========================================================
echo       SAQR ENGINE v6.2.3 - TELEGRAM ^& BINANCE BRIDGE
echo ========================================================
echo   Folder: %CD%
echo.

if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"

if exist "saqr.env" (
  copy /Y "saqr.env" ".env" >nul
  echo [+] synced saqr.env -^> .env
)

if not exist ".env" (
  echo [!] ملف .env غير موجود — ضع saqr.env أو .env في هذا المجلد.
  pause
  exit /b 1
)

echo [+] جاري تحميل إعدادات البيئة...
echo [+] Paper 5000 USD ^| api.binance.com ^| Telegram bridge
echo.

set "SAQR_EXE="
if exist "bin\saqr.exe" set "SAQR_EXE=bin\saqr.exe"
if not defined SAQR_EXE if exist "saqr.exe" set "SAQR_EXE=saqr.exe"
if not defined SAQR_EXE if exist "target\release\saqr.exe" set "SAQR_EXE=target\release\saqr.exe"

if not defined SAQR_EXE (
  echo [X] saqr.exe not found — build: cargo build --release
  pause
  exit /b 1
)

echo [CHECK] %SAQR_EXE% --check
"%SAQR_EXE%" --check
if errorlevel 1 (
  echo [X] preflight failed — keys missing in .env
  pause
  exit /b 1
)

echo [+] تشغيل المحرك في هذه النافذة — ستظهر أسعار BTC والإشارات...
echo [+] Dashboard: http://127.0.0.1:8788
echo.
start "" "http://127.0.0.1:8788"

"%SAQR_EXE%"
set "EC=%ERRORLEVEL%"

echo.
echo ========================================================
echo   Engine stopped or error. Exit code: %EC%
echo ========================================================
pause
exit /b %EC%
