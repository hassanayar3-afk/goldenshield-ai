@echo off
title GoldenShield STOP
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo === ايقاف GoldenShield نهائياً ===
py scripts\lifecycle.py request-stop manual_stop

echo.
echo تم الايقاف. لن تُرسل اي اشارات ولن يعاد التشغيل تلقائيا.
echo MT5 يمكن ان يبقى مفتوحاً — اغلق نافذة 00_START اذا كانت تعمل.
echo.
pause
