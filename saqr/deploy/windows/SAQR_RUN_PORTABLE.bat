@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SAQR v6.2.3 — صقر | Live Console
cd /d "%~dp0"
set "SAQR_HOME=%CD%"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║     SAQR v6.2.3 — Paper + Live Market + TG      ║
echo  ╚══════════════════════════════════════════════════╝
echo   المسار: %SAQR_HOME%
echo.

if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"

if exist "saqr.env" (
  copy /Y "saqr.env" ".env" >nul
  echo [OK] .env synced from saqr.env
) else if not exist ".env" (
  echo [ERROR] saqr.env missing — use FULL package zip.
  goto :FAIL
)

if not exist "bin\saqr.exe" (
  echo [ERROR] bin\saqr.exe missing.
  goto :FAIL
)

where python >nul 2>&1
if %ERRORLEVEL%==0 if exist "scripts\sanitize_saqr_env.py" (
  python "scripts\sanitize_saqr_env.py" ".env" >nul 2>&1
)

where python >nul 2>&1
if %ERRORLEVEL%==0 if exist "scripts\validate_saqr_env.py" (
  python "scripts\validate_saqr_env.py" ".env"
  if errorlevel 1 goto :FAIL
)

echo [CHECK] saqr --check
"bin\saqr.exe" --check
if errorlevel 1 goto :FAIL

tasklist /FI "IMAGENAME eq saqr.exe" 2>nul | find /I "saqr.exe" >nul
if not errorlevel 1 (
  echo [WARN] saqr.exe already running — opening live console only.
  goto :LIVE
)

echo [START] Engine background — logs\console.log
start /B cmd /c "cd /d \"%SAQR_HOME%\" && \"bin\saqr.exe\" >> \"logs\console.log\" 2>&1"

:LIVE
if exist "SAQR_LIVE_CONSOLE.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SAQR_LIVE_CONSOLE.ps1"
  set "EC=%ERRORLEVEL%"
) else (
  echo [RUN] Dashboard http://127.0.0.1:8788 — engine in background
  start http://127.0.0.1:8788
  echo اضغط Ctrl+C أو أغلق النافذة. STOP_SAQR.bat لإيقاف المحرك.
  pause
  set "EC=0"
)
goto :END

:FAIL
echo.
echo ══ فشل التشغيل — راجع logs\console.log إن وُجد ══
if exist "logs\console.log" type "logs\console.log"
echo.
pause
exit /b 1

:END
pause
exit /b %EC%
