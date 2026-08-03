@echo off
chcp 65001 >nul
setlocal EnableExtensions
title GoldenShield — START BOT
color 0A

rem ============================================================
rem  START_BOT.bat
rem  تشغيل البوت الرسمي الواحد — لا يلمس قاعدة البيانات ولا التقارير
rem  المسار الوحيد: C:\GoldenShield_Binance
rem ============================================================

set "GS_ROOT=C:\GoldenShield_Binance"
set "GS_TASK=GoldenShieldBotOfficial"
set "GS_DB=%GS_ROOT%\storage\db\goldenshield.db"
set "GS_PY=C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"

echo.
echo  ========================================================
echo    GoldenShield AI  ^|  START BOT
echo    تشغيل البوت — حفظ كل الصفقات والتقارير كما هي
echo  ========================================================
echo.

if not exist "%GS_ROOT%\main.py" (
  echo  [ERROR] لم يُعثر على المشروع في: %GS_ROOT%
  pause
  exit /b 1
)
if not exist "%GS_ROOT%\.env" (
  echo  [ERROR] ملف .env غير موجود
  pause
  exit /b 1
)

cd /d "%GS_ROOT%"
set "PYTHONPATH=%GS_ROOT%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "GOLDENSHIELD_OFFICIAL_ROOT=%GS_ROOT%"
set "GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true"
set "GOLDENSHIELD_LOCK_FAIL_CLOSED=true"
set "DB_PATH=%GS_DB%"
set "BOT_FORCE_ACTIVE=true"

echo  [1/5] منع سكون ويندوز...
powercfg -change -standby-timeout-ac 0 >nul 2>&1
powercfg -change -hibernate-timeout-ac 0 >nul 2>&1

echo  [2/5] إيقاف أي نسخة مكررة فقط (بدون حذف بيانات)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' -and $_.Name -match 'python|py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; schtasks /End /TN '%GS_TASK%' /F 2>$null | Out-Null"
timeout /t 2 /nobreak >nul

echo  [3/5] إزالة أعلام الإيقاف/القفل فقط...
if exist "%GS_ROOT%\storage\runtime\user_stopped.flag" del /f /q "%GS_ROOT%\storage\runtime\user_stopped.flag" >nul 2>&1
if exist "%GS_ROOT%\storage\runtime\bot_instance.lock" del /f /q "%GS_ROOT%\storage\runtime\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1

echo  [4/5] التأكد من ملف العامل الرسمي...
if not exist "%GS_ROOT%\run_official_bot.bat" (
  echo  [ERROR] run_official_bot.bat مفقود — أعد نشر الحزمة الرسمية
  pause
  exit /b 1
)
schtasks /Query /TN "%GS_TASK%" >nul 2>&1
if errorlevel 1 (
  schtasks /Create /TN "%GS_TASK%" /TR "%GS_ROOT%\run_official_bot.bat" /SC ONSTART /RL HIGHEST /F >nul
)

echo  [5/5] تشغيل البوت...
schtasks /Run /TN "%GS_TASK%" >nul 2>&1
if errorlevel 1 (
  start "" /MIN "%GS_ROOT%\run_official_bot.bat"
)
timeout /t 6 /nobreak >nul

if exist "%GS_ROOT%\00_LIVE_CONSOLE.bat" (
  start "GoldenShield LIVE" "%GS_ROOT%\00_LIVE_CONSOLE.bat"
)

echo.
echo  --------------------------------------------------------
echo   الحالة : تم طلب التشغيل
echo   المجلد : %GS_ROOT%
echo   قاعدة البيانات : %GS_DB%
echo   ملاحظة : لم يُحذف أي خزن / صفقات / تقارير
echo  --------------------------------------------------------
echo.
echo  يمكنك اغلاق هذه النافذة — البوت يعمل في الخلفية.
timeout /t 8 /nobreak >nul
endlocal
exit /b 0
