@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8
title MT5 Python Connect Test
echo.
echo ========================================
echo   MT5 Python Connection Test
echo ========================================
echo.
echo Keep XM MT5 OPEN and logged in.
echo.
where py >nul 2>&1
if errorlevel 1 (
  set PY=python
) else (
  set PY=py
)
echo Using: %PY%
echo.
"%PY%" "%~dp0scripts\test_mt5_connect.py"
set EXITCODE=%ERRORLEVEL%
echo.
echo ExitCode=%EXITCODE%
echo.
echo Window will stay open. Send screenshot of this window.
echo.
pause
exit /b %EXITCODE%
