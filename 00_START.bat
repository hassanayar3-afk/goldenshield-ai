@echo off
title GoldenShield Supervisor
cd /d "%~dp0"
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8
echo === GoldenShield MT5/XM - auto restart ===
echo Folder: %CD%
echo build:2026-07-15-forex-mt5-first
echo.
if not exist requirements.txt (
  echo [ERROR] requirements.txt not found in this folder.
  echo Wrong folder. Extract zip fully to C:\GoldenShield
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python not installed.
    pause
    exit /b 1
  )
  set PY=python
) else (
  set PY=py
)
echo Using %PY% ...
%PY% -m pip install -r requirements.txt MetaTrader5
if errorlevel 1 (
  echo [ERROR] pip install failed
  pause
  exit /b 1
)
if not exist storage\db\backups mkdir storage\db\backups
if not exist storage\logs mkdir storage\logs
if not exist storage\runtime mkdir storage\runtime
%PY% scripts\bootstrap_storage.py
if errorlevel 1 (
  echo [ERROR] database bootstrap failed
  pause
  exit /b 1
)
%PY% scripts\lifecycle.py clear-stop
:loop
if exist storage\runtime\user_stopped.flag (
  echo [STOP] Stopped by you.
  pause
  exit /b 0
)
echo Keep MetaTrader5 OPEN and logged in to XM.
%PY% -u main.py
set EXIT_CODE=%ERRORLEVEL%
if exist storage\runtime\user_stopped.flag (
  echo [STOP] Stopped by you.
  pause
  exit /b 0
)
echo [!] Bot exited code %EXIT_CODE% - restart in 15s
timeout /t 15 /nobreak
goto loop
