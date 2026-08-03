@echo off
rem عامل الخلفية الرسمي — يُستدعى من المهمة GoldenShieldBotOfficial
rem لا تشغّل هذا الملف يدوياً إلا للتشخيص. استخدم START_BOT.bat
cd /d "C:\GoldenShield_Binance"
title GoldenShield WORKER 24/7
set "PYTHONPATH=C:\GoldenShield_Binance"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "GOLDENSHIELD_OFFICIAL_ROOT=C:\GoldenShield_Binance"
set "GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true"
set "GOLDENSHIELD_LOCK_FAIL_CLOSED=true"
set "DB_PATH=C:\GoldenShield_Binance\storage\db\goldenshield.db"
set "BOT_FORCE_ACTIVE=true"
if not exist "storage\logs" mkdir "storage\logs"
if exist "storage\runtime\user_stopped.flag" del /f /q "storage\runtime\user_stopped.flag"
set "GS_PY=C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%GS_PY%" set "GS_PY=py"
echo [%DATE% %TIME%] WORKER_START>> storage\logs\bot_stdout.log
:loop
"%GS_PY%" -u main.py >> storage\logs\bot_stdout.log 2>&1
echo [%DATE% %TIME%] WORKER_EXIT restart>> storage\logs\bot_stdout.log
timeout /t 5 /nobreak >nul
goto loop
