@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SAQR Engine v6.2.3 — صقر
cd /d "%~dp0..\.."

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   SAQR v6.2.3 — Paper + Live Market Bridge  ║
echo  ╚══════════════════════════════════════════╝
echo.

if not exist ".env" (
  if exist "saqr.env" (
    copy /Y saqr.env .env >nul
    echo [OK] Copied saqr.env to .env
  )
)
if not exist ".env" (
  if exist "saqr.env.template" (
    copy /Y saqr.env.template .env >nul
    echo [OK] Created .env from saqr.env.template — add TELEGRAM_* then restart.
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

set "VALIDATOR=scripts\validate_saqr_env.py"
if not exist "%VALIDATOR%" set "VALIDATOR=..\..\scripts\validate_saqr_env.py"
where python >nul 2>&1
if %ERRORLEVEL%==0 if exist "%VALIDATOR%" (
  python "%VALIDATOR%" ".env"
  if errorlevel 1 (
    echo [ERROR] .env preflight failed — fix keys then restart.
    pause
    exit /b 1
  )
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

if not exist "%SAQR_EXE%" (
  echo [ERROR] Build saqr.exe first: cargo build --release
  pause
  exit /b 1
)

echo [CHECK] Engine preflight...
"%SAQR_EXE%" --check
if errorlevel 1 (
  echo [ERROR] Engine --check failed. Fix .env and retry.
  pause
  exit /b 1
)

echo [RUN] Dashboard: http://127.0.0.1:8788
echo       Paper 5000 USD ^| api.binance.com ^| Telegram bridge
echo.
"%SAQR_EXE%"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" echo [EXIT] Code %EC%
pause
exit /b %EC%
