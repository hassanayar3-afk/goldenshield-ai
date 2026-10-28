@echo off
setlocal
set "GS_ROOT=%~dp0..\..\"
if exist "%~dp0..\..\main.py" set "GS_ROOT=%~dp0..\..\"
if not exist "%GS_ROOT%main.py" set "GS_ROOT=C:\GoldenShield_Binance\"
cd /d "%GS_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%deploy\windows\GS_START_FULL_STACK.ps1" -Root "%GS_ROOT:~0,-1%"
endlocal
