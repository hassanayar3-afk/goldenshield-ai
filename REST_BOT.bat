@echo off
chcp 65001 >nul
setlocal EnableExtensions
title GoldenShield — REST BOT
color 0B

set "GS_ROOT=C:\GoldenShield_Binance"
set "GS_TASK=GoldenShieldBotOfficial"
set "GS_DB=%GS_ROOT%\storage\db\goldenshield.db"
set "GS_WORKER=%GS_ROOT%\run_official_bot.ps1"
set "GS_KILL=%GS_ROOT%\scripts\_kill_gs_workers.ps1"

echo.
echo  ========================================================
echo    GoldenShield AI  ^|  REST BOT  (Restart)
echo    إعادة تشغيل منظمة — مثيل واحد مخفي
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
set "DB_PATH=%GS_DB%"
set "BOT_FORCE_ACTIVE=true"

echo  [حماية البيانات] لن يُحذف: DB / reports / logs / صفقات
echo.

echo  [1/4] إيقاف العملية والنوافذ المكررة...
schtasks /End /TN "%GS_TASK%" /F >nul 2>&1
schtasks /End /TN "GoldenShieldLiveConsole" /F >nul 2>&1
if exist "%GS_KILL%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_KILL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
)
timeout /t 3 /nobreak >nul

echo  [2/4] تحرير القفل التشغيلي فقط...
if exist "%GS_ROOT%\storage\runtime\user_stopped.flag" del /f /q "%GS_ROOT%\storage\runtime\user_stopped.flag" >nul 2>&1
if exist "%GS_ROOT%\storage\runtime\bot_instance.lock" del /f /q "%GS_ROOT%\storage\runtime\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1

echo  [3/4] التحقق من قاعدة البيانات...
if not exist "%GS_DB%" (
  echo  [ERROR] قاعدة البيانات مفقودة: %GS_DB%
  pause
  exit /b 1
)
echo    OK: %GS_DB%

echo  [4/4] تشغيل مثيل واحد مخفي...
if not exist "%GS_WORKER%" (
  echo  [ERROR] run_official_bot.ps1 مفقود
  pause
  exit /b 1
)
schtasks /Delete /TN "%GS_TASK%" /F >nul 2>&1
schtasks /Create /TN "%GS_TASK%" /TR "powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File \"%GS_WORKER%\"" /SC ONSTART /RL HIGHEST /F >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $t=Get-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA Stop; $t.Settings.Hidden=$true; $t.Settings.ExecutionTimeLimit='PT0S'; $t | Set-ScheduledTask | Out-Null } catch {}"
schtasks /Run /TN "%GS_TASK%" >nul 2>&1
timeout /t 7 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)|00_LIVE_CONSOLE\.bat|نافذة الحالة|BOT STATUS' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
schtasks /Delete /TN "GoldenShieldStatusWindow" /F >nul 2>&1
schtasks /Create /TN "GoldenShieldStatusWindow" /TR "\"%GS_ROOT%\BOT_WINDOW.bat\"" /SC ONCE /ST 00:00 /RL HIGHEST /IT /F >nul 2>&1
schtasks /Run /TN "GoldenShieldStatusWindow" >nul 2>&1
if errorlevel 1 (
  if exist "%GS_ROOT%\BOT_WINDOW.bat" start "GoldenShield BOT — يعمل" "%GS_ROOT%\BOT_WINDOW.bat"
)

echo.
echo  --------------------------------------------------------
echo   الحالة : مثيل واحد + نافذة حالة ظاهرة
echo   البيانات: كما هي
echo  --------------------------------------------------------
echo.
timeout /t 4 /nobreak >nul
endlocal
exit /b 0
