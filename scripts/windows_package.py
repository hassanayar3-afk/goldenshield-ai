"""ملفات تشغيل Windows المشتركة — zip ونشر مباشر."""

from __future__ import annotations

START_BAT = r"""@echo off
title GoldenShield Supervisor
cd /d "%~dp0"
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8
echo === GoldenShield MT5/XM - auto restart ===
echo Folder: %CD%
echo build:2026-07-18-halt-sl
echo.
echo Tip: MetaTrader5 works best with Python 3.12
echo.
if not exist requirements.txt (
  echo [ERROR] requirements.txt not found in this folder.
  echo Wrong folder. Extract zip fully to C:\GoldenShield
  pause
  exit /b 1
)
if not exist core (
  echo [ERROR] core folder missing — this is not a full project zip.
  echo Extract GOLDENSHIELD_MT5_WINDOWS.zip to C:\GoldenShield then run 00_START.bat
  pause
  exit /b 1
)
if not exist main.py (
  echo [ERROR] main.py missing
  pause
  exit /b 1
)
set PY=
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 set PY=py -3.12
if not defined PY (
  py -3.11 -c "import sys" >nul 2>&1
  if not errorlevel 1 set PY=py -3.11
)
if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set PY=py
)
if not defined PY (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python not installed.
    echo Install Python 3.12 from python.org with Add to PATH
    pause
    exit /b 1
  )
  set PY=python
)
echo Using %PY% ...
%PY% -m pip install -r requirements.txt MetaTrader5
if errorlevel 1 (
  echo [ERROR] pip install failed
  pause
  exit /b 1
)
if not exist storage\db\backups mkdir storage\db\backups
if not exist storage\logs mkdir storage\logs
if not exist storage\runtime mkdir storage\runtime
%PY% scripts\bootstrap_storage.py
if errorlevel 1 (
  echo [ERROR] database bootstrap failed
  pause
  exit /b 1
)
%PY% scripts\lifecycle.py clear-stop
:loop
if exist storage\runtime\user_stopped.flag (
  echo [STOP] Stopped by you.
  pause
  exit /b 0
)
echo Keep MetaTrader5 OPEN and logged in to XM.
%PY% -u main.py
set EXIT_CODE=%ERRORLEVEL%
if exist storage\runtime\user_stopped.flag (
  echo [STOP] Stopped by you.
  pause
  exit /b 0
)
echo [!] Bot exited code %EXIT_CODE% - restart in 15s
timeout /t 15 /nobreak
goto loop
"""

STOP_BAT = r"""@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
py scripts\lifecycle.py request-stop manual_stop
echo Stopped. No signals. No auto restart.
pause
"""

CHECK_BAT = r"""@echo off
title GoldenShield - فحص المجلد
cd /d "%~dp0"
echo Folder: %CD%
echo.
set OK=1
for %%F in (requirements.txt main.py .env config scripts core execution risk) do (
  if exist %%F (
    echo [OK] %%F
  ) else (
    echo [MISSING] %%F
    set OK=0
  )
)
echo.
if "%OK%"=="1" (
  echo Folder is READY. Run 00_START.bat
) else (
  echo Folder is WRONG. Re-extract zip to C:\GoldenShield
)
pause
"""


def production_env(local: dict[str, str]) -> str:
    return "\n".join(
        [
            "ENV=production",
            "EXECUTION_MODE=live",
            "EXECUTION_BACKEND=mt5",
            "MT5_ENABLED=true",
            "BINANCE_API_KEY=",
            "BINANCE_API_SECRET=",
            f"MT5_LOGIN={local.get('MT5_LOGIN', '345814054')}",
            f"MT5_PASSWORD={local.get('MT5_PASSWORD', '')}",
            # تأكيد XM support: السيرفر الصحيح XMGlobal-MT5 10
            "MT5_SERVER=XMGlobal-MT5 10",
            "MT5_BROKER=XM",
            r"MT5_TERMINAL_PATH=C:\Program Files\XM MT5\terminal64.exe",
            "TELEGRAM_SEND_CYCLE_SIGNALS=false",
            "TELEGRAM_SIGNALS_ONLY=true",
            "LOOP_INTERVAL_SECONDS=15",
            "MANUAL_ENTRY_REQUIRED=false",
            "AUTO_ENTRY_MIN_PERCENT=95",
            "HIGH_CONVICTION_MODE=false",
            "STANDARD_BONUS_PROFILE=false",
            "MAX_CONCURRENT_POSITIONS=12",
            "TRIAL_MODE=true",
            "TRIAL_JOURNAL_ENABLED=true",
            "MT5_ATTACH_SL_TP=true",
            "BOT_ADMIN_FULL_ACCESS=true",
            "BOT_AUTO_SYNC_MT5=true",
            f"TELEGRAM_TOKEN={local.get('TELEGRAM_TOKEN', '')}",
            f"TELEGRAM_BOT_USERNAME={local.get('TELEGRAM_BOT_USERNAME', 'GoldenShield_2026_bot')}",
            f"TELEGRAM_CHAT_ID={local.get('TELEGRAM_CHAT_ID', '')}",
            f"TELEGRAM_BACKUP_CHANNEL_ID={local.get('TELEGRAM_BACKUP_CHANNEL_ID', '-1004462420308')}",
            "DB_PATH=storage/db/goldenshield.db",
        ]
    ) + "\n"
