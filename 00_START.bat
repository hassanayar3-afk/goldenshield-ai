@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title GoldenShield Binance Demo - DO NOT CLOSE
cd /d "%~dp0"

echo ============================================================
echo   GoldenShield AI - Binance Demo ONLY
echo   Folder: %CD%
echo ============================================================
echo.

if not exist "main.py" (
  echo [ERROR] main.py not found in this folder.
  echo Extract the ZIP fully, then run 00_START from inside the folder.
  echo Example: C:\GoldenShield_Binance\00_START.bat
  echo.
  pause
  exit /b 1
)

if not exist ".env" (
  echo [ERROR] .env missing.
  echo Extract the clean Binance Demo package again.
  echo.
  pause
  exit /b 1
)

if not exist "storage\runtime" mkdir "storage\runtime" >nul 2>&1
if not exist "storage\logs" mkdir "storage\logs" >nul 2>&1
if exist "storage\runtime\user_stopped.flag" (
  echo [INFO] Removing old user_stopped.flag so bot does not exit immediately
  del /f /q "storage\runtime\user_stopped.flag" >nul 2>&1
)

set "PYEXE="

REM Prefer real python.exe on PATH (skip WindowsApps store stub if broken)
for /f "delims=" %%i in ('where python 2^>nul') do (
  if not defined PYEXE (
    echo %%i | find /i "\WindowsApps\" >nul
    if errorlevel 1 (
      "%%i" -c "import sys" >nul 2>&1
      if not errorlevel 1 set "PYEXE=%%i"
    )
  )
)

if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYEXE if exist "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe" set "PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "C:\Python313\python.exe" set "PYEXE=C:\Python313\python.exe"
if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"

if not defined PYEXE (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYEXE=py -3"
  )
)

if not defined PYEXE (
  echo [ERROR] Python not found.
  echo Install Python 3.12/3.13 from python.org
  echo Enable: Add python.exe to PATH
  echo Then run this file again.
  echo.
  pause
  exit /b 1
)

echo [OK] Python: !PYEXE!
if "!PYEXE!"=="py -3" (
  py -3 -c "import sys; print('[OK] version', sys.version)"
) else (
  "!PYEXE!" -c "import sys; print('[OK] version', sys.version)"
)
if errorlevel 1 (
  echo [ERROR] Python cannot run.
  pause
  exit /b 1
)

echo.
echo [1/3] Installing requirements (first run may take 1-2 minutes)...
if "!PYEXE!"=="py -3" (
  py -3 -m pip install -r requirements.txt
) else (
  "!PYEXE!" -m pip install -r requirements.txt
)
if errorlevel 1 echo [WARN] pip had issues - continuing if packages already exist

echo.
echo [2/3] Bootstrap storage...
if exist "scripts\bootstrap_storage.py" (
  if "!PYEXE!"=="py -3" (
    py -3 scripts\bootstrap_storage.py
  ) else (
    "!PYEXE!" scripts\bootstrap_storage.py
  )
)

echo.
echo [3/3] Starting bot...
echo ------------------------------------------------------------
echo   KEEP THIS WINDOW OPEN
echo   Telegram signals appear within about 1 minute
echo   Stop: close window OR run 00_STOP.bat
echo ------------------------------------------------------------
echo.

set "PYTHONPATH=%CD%"
set "PYTHONIOENCODING=utf-8"

:loop
echo [%DATE% %TIME%] starting main.py ...
if "!PYEXE!"=="py -3" (
  py -3 -u main.py
) else (
  "!PYEXE!" -u main.py
)
set "EC=!ERRORLEVEL!"
echo.
echo [%DATE% %TIME%] bot stopped - exit code !EC!
if exist "storage\runtime\user_stopped.flag" (
  echo Stopped by user flag - will NOT auto-restart.
  echo Delete storage\runtime\user_stopped.flag or run 00_START again.
  echo.
  pause
  exit /b 0
)
echo Restarting in 8 seconds... ^(Ctrl+C to cancel^)
timeout /t 8 /nobreak
goto loop
