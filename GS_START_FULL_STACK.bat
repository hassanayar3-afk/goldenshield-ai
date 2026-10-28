@echo off
setlocal
set "GS_ROOT=%~dp0"
if "%GS_ROOT:~-1%"=="\" set "GS_ROOT=%GS_ROOT:~0,-1%"
cd /d "%GS_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\deploy\windows\GS_START_FULL_STACK.ps1" -Root "%GS_ROOT%"
endlocal
