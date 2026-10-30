@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SAQR v6.2.3 — صقر | Control Terminal
cd /d "%~dp0"
set "SAQR_HOME=%CD%"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║     SAQR v6.2.3 — Paper + Live Market + TG      ║
echo  ╚══════════════════════════════════════════════════╝
echo   المسار: %SAQR_HOME%
echo.

if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"

rem ── حقن .env من الحزمة (saqr.env مكتوب مسبقاً — لا template فارغ) ──
if exist "saqr.env" (
  copy /Y "saqr.env" ".env" >nul
  echo [OK] .env synced from saqr.env ^(Binance + Telegram^)
) else if exist ".env" (
  echo [OK] using existing .env
) else (
  echo [ERROR] saqr.env missing — package incomplete.
  pause
  exit /b 10
)

if not exist "bin\saqr.exe" (
  echo [ERROR] bin\saqr.exe missing — package incomplete.
  pause
  exit /b 11
)

if exist "scripts\sanitize_saqr_env.py" (
  where python >nul 2>&1
  if not errorlevel 1 (
    python "scripts\sanitize_saqr_env.py" ".env" >nul 2>&1
    echo [OK] .env sanitized
  )
)

if exist "scripts\validate_saqr_env.py" (
  where python >nul 2>&1
  if not errorlevel 1 (
    python "scripts\validate_saqr_env.py" ".env"
    if errorlevel 1 (
      echo [ERROR] .env incomplete — keys empty or truncated.
      pause
      exit /b 12
    )
  )
)

echo [CHECK] saqr engine preflight...
"bin\saqr.exe" --check
if errorlevel 1 (
  echo [ERROR] Engine --check failed.
  pause
  exit /b 13
)

echo.
echo  [RUN] Dashboard: http://127.0.0.1:8788
echo        Paper 5000 USD ^| api.binance.com ^| Telegram bridge
echo.
"bin\saqr.exe"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" echo [EXIT] Code %EC%
pause
exit /b %EC%
