@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SAQR Engine v6.2.3 — صقر
cd /d "%~dp0..\.."

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   SAQR v6.2.3 — Live Integrated Testnet   ║
echo  ╚══════════════════════════════════════════╝
echo.

if not exist ".env" (
  if exist "saqr.env" (
    copy /Y saqr.env .env >nul
    echo [OK] Copied saqr.env to .env
  )
)
if not exist ".env" (
  echo [ERROR] Missing .env in: %CD%
  echo         Copy saqr.env.template to .env and fill credentials.
  pause
  exit /b 1
)

set "SANITIZER=scripts\sanitize_saqr_env.py"
if not exist "%SANITIZER%" set "SANITIZER=..\..\scripts\sanitize_saqr_env.py"
where python >nul 2>&1
if %ERRORLEVEL%==0 if exist "%SANITIZER%" (
  python "%SANITIZER%" ".env" >nul 2>&1
  echo [OK] .env sanitized (ZWSP, Telegram +, defaults)
)

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
set "SAQR_EXE=target\release\saqr.exe"

if not exist "%SAQR_EXE%" (
  echo [BUILD] First run — compiling release binary...
  cargo build --release
  if errorlevel 1 (
    echo [ERROR] cargo build failed.
    pause
    exit /b 1
  )
)

echo [RUN] Dashboard: http://127.0.0.1:8788
echo.
"%SAQR_EXE%"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" echo [EXIT] Code %EC%
pause
exit /b %EC%
