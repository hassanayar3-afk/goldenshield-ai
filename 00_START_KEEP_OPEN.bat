@echo off
REM Opens classic CMD window that stays open (not PowerShell)
cd /d "%~dp0"
start "GoldenShield Binance Demo" /D "%~dp0" cmd.exe /k "00_START.bat"
