@echo off
rem نافذة الحالة — تفتح PowerShell ثابتة (بدون تجميد Select / بدون رموز مكسورة)
cd /d "C:\GoldenShield_Binance"
title GoldenShield BOT STATUS
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0BOT_WINDOW.ps1"
