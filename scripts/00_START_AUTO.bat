@echo off
title GoldenShield Supervisor
cd /d "%~dp0"
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8

echo === GoldenShield — تشغيل تلقائي مع إعادة التشغيل ===
echo عند انقطاع النت او توقف غير مقصود: يعيد التشغيل تلقائيا
echo للايقاف الكامل: 00_STOP.bat او زر الطوارئ في تيليجرام
echo.

py -m pip install -r requirements.txt MetaTrader5 -q 2>nul
if not exist storage\db\backups mkdir storage\db\backups
if not exist storage\logs mkdir storage\logs
if not exist storage\runtime mkdir storage\runtime

REM المستخدم شغّل START عمداً — امسح علامة الايقاف السابقة
py scripts\lifecycle.py clear-stop

:loop
if exist storage\runtime\user_stopped.flag (
  echo.
  echo [STOP] البوت متوقف بقرارك — لن يعاد التشغيل تلقائيا.
  echo لتشغيله مجدداً: شغّل 00_START.bat مرة اخرى.
  pause
  exit /b 0
)

echo [%date% %time%] تشغيل GoldenShield...
py -u main.py
set EXIT_CODE=%ERRORLEVEL%

if exist storage\runtime\user_stopped.flag (
  echo.
  echo [STOP] تم الايقاف بقرارك — لا اعادة تشغيل.
  pause
  exit /b 0
)

echo.
echo [!] توقف غير مقصود (كود %EXIT_CODE%) — اعادة التشغيل خلال 15 ثانية...
echo     اضغط Ctrl+C الان اذا تريد الايقاف الكامل ثم شغّل 00_STOP.bat
timeout /t 15 /nobreak
goto loop
