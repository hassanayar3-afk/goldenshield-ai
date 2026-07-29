@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
py scripts\lifecycle.py request-stop manual_stop
echo Stopped. No signals. No auto restart.
pause
