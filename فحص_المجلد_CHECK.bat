@echo off
cd /d "%~dp0"
echo === GoldenShield folder check ===
if not exist main.py (
  echo ERROR: main.py missing
  pause
  exit /b 1
)
if not exist .env (
  echo ERROR: .env missing
  pause
  exit /b 1
)
echo OK: project files present
py -c "import sys; print(sys.version)"
pause
