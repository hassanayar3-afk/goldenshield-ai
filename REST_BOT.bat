@echo off
chcp 65001 >nul
setlocal EnableExtensions
title GoldenShield — REST BOT
color 0B

rem ============================================================
rem  REST_BOT.bat  (Restart)
rem  إعادة تشغيل البوت فقط
rem  ممنوع حذف: قاعدة البيانات / الصفقات / التقارير / السجلات
rem ============================================================

set "GS_ROOT=C:\GoldenShield_Binance"
set "GS_TASK=GoldenShieldBotOfficial"
set "GS_DB=%GS_ROOT%\storage\db\goldenshield.db"

echo.
echo  ========================================================
echo    GoldenShield AI  ^|  REST BOT  (Restart)
echo    إعادة تشغيل فقط — لا مسح لأي خزن أو صفقات أو تقارير
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

echo  [حماية البيانات]
echo    - لن يُحذف: %GS_DB%
echo    - لن يُحذف: storage\reports\
echo    - لن يُحذف: storage\logs\  (عدا القفل التشغيلي فقط)
echo.

echo  [1/4] إيقاف العملية الحالية...
schtasks /End /TN "%GS_TASK%" /F >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' -and $_.Name -match 'python|py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 3 /nobreak >nul

echo  [2/4] تحرير القفل التشغيلي فقط (بدون مسح DB/تقارير)...
if exist "%GS_ROOT%\storage\runtime\user_stopped.flag" del /f /q "%GS_ROOT%\storage\runtime\user_stopped.flag" >nul 2>&1
if exist "%GS_ROOT%\storage\runtime\bot_instance.lock" del /f /q "%GS_ROOT%\storage\runtime\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1

echo  [3/4] التحقق أن قاعدة البيانات ما زالت موجودة...
if not exist "%GS_DB%" (
  echo  [ERROR] قاعدة البيانات مفقودة — تم الإيقاف للحماية: %GS_DB%
  pause
  exit /b 1
)
echo    OK: %GS_DB%

echo  [4/4] تشغيل نفس البوت من جديد...
schtasks /Query /TN "%GS_TASK%" >nul 2>&1
if errorlevel 1 (
  if exist "%GS_ROOT%\run_official_bot.bat" (
    schtasks /Create /TN "%GS_TASK%" /TR "%GS_ROOT%\run_official_bot.bat" /SC ONSTART /RL HIGHEST /F >nul
  )
)
schtasks /Run /TN "%GS_TASK%" >nul 2>&1
if errorlevel 1 (
  if exist "%GS_ROOT%\run_official_bot.bat" start "" /MIN "%GS_ROOT%\run_official_bot.bat"
)
timeout /t 6 /nobreak >nul

echo.
echo  --------------------------------------------------------
echo   الحالة : تمت إعادة التشغيل
echo   البيانات: كما هي (صفقات + تقارير + أرشيف)
echo   للإيقاف : STOP_BOT.bat
echo   للتشغيل : START_BOT.bat
echo  --------------------------------------------------------
echo.
timeout /t 8 /nobreak >nul
endlocal
exit /b 0
