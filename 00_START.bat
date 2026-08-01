@echo off
chcp 65001 >nul
title GoldenShield Binance Demo
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
set "PYTHONIOENCODING=utf-8"
echo === GoldenShield Binance Demo ===
echo Folder: %CD%
echo.
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
echo Installing requirements once...
"%GS_PY%" -m pip install -r requirements.txt
if exist "scripts\bootstrap_storage.py" "%GS_PY%" scripts\bootstrap_storage.py
echo.
echo Starting bot - keep this window open
echo.
:loop
"%GS_PY%" -u main.py
echo.
echo Bot exited - restart in 5s
timeout /t 5 /nobreak >nul
goto loop

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
