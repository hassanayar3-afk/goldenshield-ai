@echo off
chcp 65001 >nul
setlocal EnableExtensions
title GoldenShield — START BOT
color 0A

rem ============================================================
rem  START_BOT.bat — تشغيل رسمي موحّد v2026.08 ENTERPRISE FULL
rem  مثيل واحد مخفي + نافذة حالة واحدة
rem  قواعد: 5000 / 25$ / هجين 70-90 / SSoT / Pipeline / Post-Mortem / CB
rem ============================================================

set "GS_ROOT=C:\GoldenShield_Binance"
set "GS_TASK=GoldenShieldBotOfficial"
set "GS_DB=%GS_ROOT%\storage\db\goldenshield.db"
set "GS_WORKER=%GS_ROOT%\run_official_bot.ps1"
set "GS_KILL=%GS_ROOT%\scripts\_kill_gs_workers.ps1"
set "GS_MARKER=GS_LAUNCHER_v2026_08_ENTERPRISE_FULL"

echo.
echo  ========================================================
echo    GoldenShield AI  ^|  START BOT  (%GS_MARKER%)
echo    مؤسسة ذاتية كاملة ^| هجين 70/90 ^| مثيل واحد
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
if not exist "%GS_WORKER%" (
  echo  [ERROR] run_official_bot.ps1 مفقود
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
if not defined HYBRID_SIGNAL_MODE set "HYBRID_SIGNAL_MODE=true"
if not defined PROJECT_REFERENCE_CAPITAL set "PROJECT_REFERENCE_CAPITAL=5000"
if not defined PROJECT_MIN_TRADE_NOTIONAL set "PROJECT_MIN_TRADE_NOTIONAL=25"
if not defined PROJECT_MIN_EXCHANGE_NOTIONAL set "PROJECT_MIN_EXCHANGE_NOTIONAL=5"
if not defined AUTO_ENTRY_MIN_PERCENT set "AUTO_ENTRY_MIN_PERCENT=90"
if not defined TELEGRAM_SIGNAL_MIN_PERCENT set "TELEGRAM_SIGNAL_MIN_PERCENT=70"
if not defined MANUAL_ENTRY_REQUIRED set "MANUAL_ENTRY_REQUIRED=false"
if not defined TELEGRAM_LIVE_SIGNALS set "TELEGRAM_LIVE_SIGNALS=true"
if not defined NO_SLEEP_MODE set "NO_SLEEP_MODE=true"
if not defined LOOP_INTERVAL_SECONDS set "LOOP_INTERVAL_SECONDS=4"
if not defined TELEGRAM_LIVE_SIGNALS_SECONDS set "TELEGRAM_LIVE_SIGNALS_SECONDS=4"
if not defined TELEGRAM_LIVE_POSITIONS_SECONDS set "TELEGRAM_LIVE_POSITIONS_SECONDS=3"
if not defined ENTERPRISE_PIPELINE_ENABLED set "ENTERPRISE_PIPELINE_ENABLED=true"
if not defined SSOT_SYNC_ENABLED set "SSOT_SYNC_ENABLED=true"
if not defined POST_MORTEM_ENGINE_ACTIVE set "POST_MORTEM_ENGINE_ACTIVE=true"
if not defined CIRCUIT_BREAKER_MAX_LOSSES set "CIRCUIT_BREAKER_MAX_LOSSES=3"

echo  [1/6] منع سكون ويندوز...
powercfg -change -standby-timeout-ac 0 >nul 2>&1
powercfg -change -hibernate-timeout-ac 0 >nul 2>&1

echo  [2/6] إيقاف العمال القدامى/النوافذ المكررة...
schtasks /End /TN "%GS_TASK%" /F >nul 2>&1
schtasks /End /TN "GoldenShieldLiveConsole" /F >nul 2>&1
schtasks /Change /TN "GoldenShieldLiveConsole" /DISABLE >nul 2>&1
schtasks /End /TN "GoldenShieldStatusWindow" /F >nul 2>&1
if exist "%GS_KILL%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_KILL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot|BOT_WINDOW' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
)
timeout /t 2 /nobreak >nul

echo  [3/6] تنظيف أقفال تشغيل فقط (لا يمس DB/التقارير/الصفقات)...
if exist "%GS_ROOT%\storage\runtime\user_stopped.flag" del /f /q "%GS_ROOT%\storage\runtime\user_stopped.flag" >nul 2>&1
if exist "%GS_ROOT%\storage\runtime\bot_instance.lock" del /f /q "%GS_ROOT%\storage\runtime\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1
del /f /q "%GS_ROOT%\storage\runtime\*.tmp" >nul 2>&1
del /f /q "%GS_ROOT%\storage\runtime\*.temp" >nul 2>&1

echo  [4/6] التحقق من الملفات الأساسية...
if not exist "%GS_ROOT%\config\project_rules.py" (
  echo  [WARN] project_rules.py غير موجود — أكمل النشر أولاً
)
if not exist "%GS_DB%" (
  echo  [WARN] قاعدة البيانات ستُنشأ عند أول تشغيل إن لزم
) else (
  echo    DB OK: %GS_DB%
)

echo  [5/6] تسجيل المهمة الرسمية المخفية...
schtasks /Delete /TN "%GS_TASK%" /F >nul 2>&1
schtasks /Create /TN "%GS_TASK%" /TR "powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File \"%GS_WORKER%\"" /SC ONSTART /RL HIGHEST /F >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $t=Get-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA Stop; $t.Settings.Hidden=$true; $t.Settings.ExecutionTimeLimit='PT0S'; $t | Set-ScheduledTask | Out-Null } catch {}"

echo  [6/6] تشغيل البوت + نافذة الحالة...
schtasks /Run /TN "%GS_TASK%" >nul 2>&1
timeout /t 8 /nobreak >nul

rem نافذة CMD ظاهرة مباشرة (أوضح من schtasks /IT على VPS/RDP)
echo  [CMD] فتح نافذة مراقبة الإشارات الحية...
schtasks /End /TN "GoldenShieldStatusWindow" /F >nul 2>&1
schtasks /Delete /TN "GoldenShieldStatusWindow" /F >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)|00_LIVE_CONSOLE\.bat|BOT STATUS|LIVE SIGNALS' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
timeout /t 1 /nobreak >nul
if exist "%GS_ROOT%\BOT_WINDOW.bat" (
  start "GoldenShield LIVE SIGNALS" /D "%GS_ROOT%" cmd /k call "%GS_ROOT%\BOT_WINDOW.bat"
) else if exist "%GS_ROOT%\00_LIVE_CONSOLE.bat" (
  start "GoldenShield LIVE CONSOLE" /D "%GS_ROOT%" cmd /k call "%GS_ROOT%\00_LIVE_CONSOLE.bat"
) else (
  echo  [WARN] BOT_WINDOW.bat غير موجود
)

echo.
echo  --------------------------------------------------------
echo   الحالة : البوت يعمل + نافذة CMD واحدة للمراقبة
echo   المجلد : %GS_ROOT%
echo   العامل : %GS_WORKER%
echo   القواعد: 5000 / 25$ / هجين 70-90 / SSoT / Pipeline / PM
echo   ملاحظة : نافذة LIVE SIGNALS تُفتح تلقائياً — إغلاقها لا يوقف البوت
echo  --------------------------------------------------------
echo.
timeout /t 4 /nobreak >nul
endlocal
exit /b 0
