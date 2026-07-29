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
echo Prefer Python 3.12 for MetaTrader5
echo Keep XM MT5 OPEN and logged in.
echo.

set PY=
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 set PY=py -3.12

if not defined PY (
  py -3.11 -c "import sys" >nul 2>&1
  if not errorlevel 1 set PY=py -3.11
)

if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set PY=py
)

if not defined PY set PY=python

echo Using: %PY%
echo.
%PY% -m pip install --quiet MetaTrader5
%PY% "%~dp0scripts\test_mt5_connect.py"
set EXITCODE=%ERRORLEVEL%
echo.
echo ExitCode=%EXITCODE%
echo.
echo Window stays open. Send screenshot.
echo.
pause
exit /b %EXITCODE%
