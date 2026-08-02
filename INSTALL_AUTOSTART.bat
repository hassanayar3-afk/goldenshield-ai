@echo off
title GoldenShield - Autostart policy
cd /d "%~dp0"

echo === GoldenShield Autostart ===
echo Duplicate WindowsBoot registration is DISABLED.
echo Use ONE starter only:
echo   - Task: GoldenShieldBotOfficial
echo   - Or:   C:\GoldenShield_Binance\00_START.bat
echo.
echo Unregistering legacy task GoldenShield_WindowsBoot (if any)...
powershell -ExecutionPolicy Bypass -File "%~dp0deployment\unregister_autostart.ps1" 2>nul
echo.
echo Done. Do NOT install a second autostart task.
pause
