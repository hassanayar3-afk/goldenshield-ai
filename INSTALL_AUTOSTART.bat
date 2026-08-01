@echo off
title GoldenShield - تثبيت التشغيل التلقائي
cd /d "%~dp0"

echo === تثبيت تشغيل GoldenShield تلقائياً مع Windows ===
echo يشغّل: قاعدة البيانات + بوت Binance
echo.
echo يتطلب صلاحيات مسؤول...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0deployment\register_autostart.ps1"
if errorlevel 1 (
  echo.
  echo فشل — شغّل هذا الملف بزر يمين ^> Run as administrator
  pause
  exit /b 1
)

echo.
echo تم التثبيت. عند اعادة تشغيل Windows سيبدأ GoldenShield تلقائياً.
echo للتعطيل: deployment\unregister_autostart.ps1
pause
