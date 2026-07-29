@echo off
title GoldenShield Windows Boot
cd /d "%~dp0\.."
set PYTHONIOENCODING=utf-8
set GOLDENSHIELD_BOOT=1

echo === GoldenShield - تشغيل تلقائي عند فتح Windows ===
echo 1) قاعدة البيانات  2) MT5  3) بوت الاشارات
echo.

py scripts\windows_boot.py full
if errorlevel 1 (
  echo [!] فشل التشغيل التلقائي — راجع storage\logs
  exit /b 1
)
echo [OK] تم بدء النظام في نافذة منفصلة.
exit /b 0
