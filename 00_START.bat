@echo off
chcp 65001 >nul
title GoldenShield Binance Demo
cd /d "%~dp0"
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8
echo === GoldenShield Binance Demo ===
echo Folder: %CD%
echo.
if not exist main.py (
  echo [ERROR] main.py missing — extract ZIP fully to this folder
  pause
  exit /b 1
)
if not exist .env (
  echo [ERROR] .env missing
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python not installed
    pause
    exit /b 1
  )
  set PY=python
) else (
  set PY=py
)
echo Installing requirements once...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [WARN] pip install had issues — continuing
)
if exist scripts\bootstrap_storage.py (
  %PY% scripts\bootstrap_storage.py
)
echo.
echo Starting bot (Ctrl+C to stop loop)...
:loop
%PY% -u main.py
echo.
echo Bot exited — restart in 5s
timeout /t 5 /nobreak >nul
goto loop
