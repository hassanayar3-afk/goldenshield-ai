@echo off
setlocal EnableExtensions
title GoldenShield — START 24/7 FULL STACK
set "GS_ROOT=%~dp0"
if "%GS_ROOT:~-1%"=="\" set "GS_ROOT=%GS_ROOT:~0,-1%"
if not exist "%GS_ROOT%\main.py" set "GS_ROOT=C:\GoldenShield_Binance"
cd /d "%GS_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\deploy\windows\GS_START_FULL_STACK.ps1" -Root "%GS_ROOT%"
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
