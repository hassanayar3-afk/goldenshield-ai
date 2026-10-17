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

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
  echo [Saqr] WARNING: Port 8000 is already in use ^(PID %%P^).
  echo [Saqr] Close the other Saqr/Python window or run: taskkill /PID %%P /F
  echo [Saqr] Or change MOBILE_API_PORT and TERMINAL_WS_PORT in .env
  pause
  exit /b 3
)

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
