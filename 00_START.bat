@echo off
chcp 65001 >nul
title GoldenShield Binance Demo
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
set "PYTHONIOENCODING=utf-8"
set "GOLDENSHIELD_OFFICIAL_ROOT=C:\GoldenShield_Binance"
set "GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true"
set "GOLDENSHIELD_LOCK_FAIL_CLOSED=true"

echo === GoldenShield Binance Demo ===
echo Folder: %CD%
echo.

echo %CD% | find /I "Telegram Desktop" >nul
if not errorlevel 1 goto :bad_path
echo %CD% | find /I "\Downloads\" >nul
if not errorlevel 1 goto :bad_path

if /I not "%CD%"=="C:\GoldenShield_Binance" (
  if exist "C:\GoldenShield_Binance\main.py" (
    echo [WARN] Wrong folder. Switching to C:\GoldenShield_Binance
    cd /d "C:\GoldenShield_Binance"
    set "PYTHONPATH=C:\GoldenShield_Binance"
  )
)

if not exist "main.py" goto :missing_main
if not exist ".env" goto :missing_env
set "GS_PY="
where py >nul 2>&1
if not errorlevel 1 set "GS_PY=py"
if not defined GS_PY (
  where python >nul 2>&1
  if not errorlevel 1 set "GS_PY=python"
)
if not defined GS_PY goto :missing_python

echo Stopping any duplicate bot copies...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' -and $_.Name -match 'python|py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

echo Installing requirements once...
"%GS_PY%" -m pip install -r requirements.txt
if exist "scripts\bootstrap_storage.py" "%GS_PY%" scripts\bootstrap_storage.py
echo.
echo Starting SINGLE bot - keep this window open
echo.
:loop
"%GS_PY%" -u main.py
echo.
echo Bot exited - restart in 5s
timeout /t 5 /nobreak >nul
goto loop

:bad_path
echo [ERROR] Do NOT run from Telegram Downloads.
echo Extract/run only from: C:\GoldenShield_Binance
pause
exit /b 1

:missing_main
echo [ERROR] main.py missing - extract ZIP fully to C:\GoldenShield_Binance
pause
exit /b 1

:missing_env
echo [ERROR] .env missing
pause
exit /b 1

:missing_python
echo [ERROR] Python not installed
pause
exit /b 1
