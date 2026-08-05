@echo off
REM Compatibility — prefer live_console.ps1
cd /d "%~dp0"
if exist "%~dp0live_console.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0live_console.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0BOT_WINDOW.ps1"
)
