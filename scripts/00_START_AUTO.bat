@echo off
title GoldenShield Supervisor
REM Always run from repo root (parent of scripts\), never from scripts\ itself
cd /d "%~dp0.."
set "PYTHONPATH=%CD%"
set "PYTHONIOENCODING=utf-8"
set "GOLDENSHIELD_OFFICIAL_ROOT=C:\GoldenShield_Binance"

echo === GoldenShield — تشغيل تلقائي مع إعادة التشغيل ===
echo Folder: %CD%
echo عند انقطاع النت او توقف غير مقصود: يعيد التشغيل تلقائيا
echo للايقاف الكامل: 00_STOP.bat او زر الطوارئ في تيليجرام
echo.

if not exist "main.py" (
  echo [ERROR] main.py not found. Run from project root or use C:\GoldenShield_Binance\00_START.bat
  pause
  exit /b 1
)

py -m pip install -r requirements.txt -q 2>nul
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
