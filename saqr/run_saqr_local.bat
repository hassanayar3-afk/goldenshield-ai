@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM === Saqr AI — single-folder install (e.g. C:\Saqr_Binance) ===
cd /d "%~dp0"
if errorlevel 1 (
  echo [Saqr] ERROR: Cannot set working directory.
  exit /b 1
)

if not exist "gateway\main.py" (
  echo [Saqr] ERROR: gateway\main.py not found.
  echo [Saqr] Run this file from Saqr project root ^(folder with gateway, engines, .env^).
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
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
if errorlevel 1 (
  echo [Saqr] ERROR: pip install failed.
  exit /b 1
)

if not exist "logs" mkdir logs
if not exist "database" mkdir database

set PYTHONNOUSERSITE=1
REM Runtime root wins over SAqr_ROOT inside .env (prevents path mismatch).
set "SAqr_ROOT=%CD%"

echo [Saqr] Working directory: %CD%
echo [Saqr] SAqr_ROOT=%SAqr_ROOT%

set "SAQR_PORT=8000"
for /f "usebackq tokens=2 delims==" %%A in (`findstr /B /I "MOBILE_API_PORT=" ".env" 2^>nul`) do set "SAQR_PORT=%%A"

call :free_port !SAQR_PORT!
if errorlevel 1 exit /b 3

echo [Saqr] Starting: python gateway\main.py
echo [Saqr] Local UI: http://127.0.0.1:!SAQR_PORT!
start "" http://127.0.0.1:!SAQR_PORT!/

python gateway\main.py
set EXITCODE=!ERRORLEVEL!
if not "!EXITCODE!"=="0" (
  echo [Saqr] Server exited with code !EXITCODE!
  pause
)
exit /b !EXITCODE!

:free_port
set "TARGET_PORT=%~1"
set "BUSY=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%TARGET_PORT% .*LISTENING"') do (
  set "BUSY=1"
  echo [Saqr] Port %TARGET_PORT% in use by PID %%P — stopping previous listener...
  taskkill /PID %%P /F >nul 2>&1
)
if "!BUSY!"=="1" (
  timeout /t 2 /nobreak >nul
  for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%TARGET_PORT% .*LISTENING"') do (
    echo [Saqr] ERROR: Port %TARGET_PORT% still busy ^(PID %%P^).
    echo [Saqr] Close that app manually or set MOBILE_API_PORT and TERMINAL_WS_PORT in .env
    exit /b 1
  )
  echo [Saqr] Port %TARGET_PORT% is free.
)
exit /b 0
