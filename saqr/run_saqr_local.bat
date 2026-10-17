@echo off
setlocal EnableDelayedExpansion
REM Saqr AI — unified local launcher (Windows)
REM Target install path: C:\Users\acer\saqr\

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [Saqr] Creating virtual environment...
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat

echo [Saqr] Installing dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

if not exist "logs" mkdir logs

echo [Saqr] Starting gateway (HTTP + WebSocket on port 8000)
echo [Saqr] Local: http://127.0.0.1:8000  ^|  LAN: http://YOUR_LAPTOP_IP:8000
start "" http://127.0.0.1:8000/
python -m gateway.main

endlocal
