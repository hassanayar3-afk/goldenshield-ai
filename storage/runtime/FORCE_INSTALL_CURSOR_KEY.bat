@echo off
chcp 65001 >nul
title GoldenShield - install cloud SSH key
:: تشغيل كمسؤول (جبري)
net session >nul 2>&1
if not %errorLevel%==0 (
    echo Requesting elevated rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "URL=https://raw.githubusercontent.com/hassanayar3-afk/goldenshield-ai/cursor/win-remote-deploy-fix-2e26/storage/runtime/install_cursor_ssh_key.ps1"
set "PS1=%TEMP%\gs_cursor_key_install.ps1"

echo Downloading install script...
curl -fsSL -o "%PS1%" "%URL%" 2>nul
if not exist "%PS1%" (
    powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%PS1%'"
)
if not exist "%PS1%" (
    echo FAILED download. Check internet.
    pause
    exit /b 1
)

echo Running install...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
if errorlevel 1 (
    echo FAILED install.
    pause
    exit /b 1
)

echo.
echo SUCCESS. You can close this window and write "تم" to the agent.
pause
