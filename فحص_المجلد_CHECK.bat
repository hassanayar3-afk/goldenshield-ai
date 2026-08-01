@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === فحص مجلد GoldenShield (Binance Demo) ===
echo المجلد: %CD%
echo.
if not exist main.py (
  echo ERROR: main.py غير موجود — فك الضغط في مجلد واحد ثم أعد الفحص
  pause
  exit /b 1
)
if not exist .env (
  echo ERROR: .env غير موجود
  pause
  exit /b 1
)
findstr /B /C:"EXECUTION_BACKEND=binance" .env >nul || echo WARN: EXECUTION_BACKEND يجب أن يكون binance
findstr /B /C:"BINANCE_DEMO_TRADING=true" .env >nul || echo WARN: BINANCE_DEMO_TRADING يجب أن يكون true
findstr /B /C:"MT5_ENABLED=true" .env >nul && echo WARN: MT5_ENABLED=true — يجب false
echo.
where python >nul 2>&1 && python -c "import sys; print('python', sys.version)" 2>nul
where py >nul 2>&1 && py -3 -c "import sys; print('py -3', sys.version)" 2>nul
echo.
echo OK إن ظهر main.py و.env وPython أعلاه.
pause
