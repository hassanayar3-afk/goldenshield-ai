@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM === Saqr AI — C:\Users\acer\saqr ===
cd /d "%~dp0"
if errorlevel 1 (
  echo [Saqr] ERROR: Cannot set working directory.
  exit /b 1
)

if not exist "gateway\main.py" (
  echo [Saqr] ERROR: gateway\main.py not found.
  echo [Saqr] Run this file from project root: C:\Users\acer\saqr
  exit /b 1
)

if not exist "requirements.txt" (
  echo [Saqr] ERROR: requirements.txt missing.
  exit /b 1
)

where py >nul 2>&1
if errorlevel 1 (
  echo [Saqr] ERROR: Python launcher 'py' not found. Install Python 3.10+.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [Saqr] Creating virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo [Saqr] ERROR: venv creation failed.
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [Saqr] ERROR: Cannot activate .venv
  exit /b 1
)

echo [Saqr] Installing / updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo [Saqr] ERROR: pip install failed.
  exit /b 1
)

if not exist "logs" mkdir logs
if not exist "database" mkdir database

set PYTHONNOUSERSITE=1
set "SAQR_ROOT=%CD%"

echo [Saqr] Working directory: %CD%
echo [Saqr] Starting: python gateway\main.py
echo [Saqr] Local UI: http://127.0.0.1:8000
start "" http://127.0.0.1:8000/

python gateway\main.py
set EXITCODE=!ERRORLEVEL!
if not "!EXITCODE!"=="0" (
  echo [Saqr] Server exited with code !EXITCODE!
  pause
)
exit /b !EXITCODE!
