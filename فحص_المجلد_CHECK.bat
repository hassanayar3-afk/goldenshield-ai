@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === GoldenShield folder check (Binance Demo) ===
if not exist main.py (
  echo ERROR: main.py missing
  echo Extract package to this folder then run 00_START.bat
  pause
  exit /b 1
)
if not exist .env (
  echo ERROR: .env missing
  pause
  exit /b 1
)
findstr /B /C:"EXECUTION_BACKEND=binance" .env >nul || echo WARN: EXECUTION_BACKEND should be binance
findstr /B /C:"BINANCE_DEMO_TRADING=true" .env >nul || echo WARN: BINANCE_DEMO_TRADING should be true
findstr /B /C:"MT5_ENABLED=true" .env >nul && echo WARN: MT5_ENABLED=true — should be false
echo OK: project files present
py -c "import sys; print(sys.version)"
pause
