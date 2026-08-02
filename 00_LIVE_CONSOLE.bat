@echo off
chcp 65001 >nul
title GoldenShield LIVE VIEW - اغلاق هذه النافذة لا يوقف البوت
cd /d "%~dp0"
color 0A
echo ============================================================
echo   GoldenShield LIVE CONSOLE  (عرض فقط)
echo   البوت يعمل 24 ساعة في الخلفية عبر المهمة الرسمية
echo   اغلاق هذه النافذة = اغلاق العرض فقط، البوت يستمر
echo   المجلد: %CD%
echo ============================================================
echo.

:waitlog
if not exist "storage\logs\bot_stdout.log" (
  echo [%DATE% %TIME%] بانتظار سجل البوت... تأكد أن المهمة GoldenShieldBotOfficial تعمل
  timeout /t 5 /nobreak >nul
  goto waitlog
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$log='storage\logs\bot_stdout.log'; " ^
  "Write-Host '--- بث السجل الحي (آخر 50 سطراً ثم مستمر) ---' -ForegroundColor Green; " ^
  "Get-Content -Path $log -Tail 50 -Wait -ErrorAction SilentlyContinue"
