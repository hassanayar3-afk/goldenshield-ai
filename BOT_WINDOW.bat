@echo off
cd /d "C:\GoldenShield_Binance"
title GoldenShield LIVE SIGNALS
powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0BOT_WINDOW.ps1"
