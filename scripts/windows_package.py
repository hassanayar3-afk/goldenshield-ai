"""حزمة تشغيل Windows — Binance Demo فقط (بدون MetaTrader)."""

from __future__ import annotations

START_BAT = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === GoldenShield Binance Demo - auto restart ===
:loop
py -u main.py
echo.
echo Bot exited — restart in 5s (Ctrl+C to stop)
timeout /t 5 /nobreak >nul
goto loop
"""

STOP_BAT = r"""@echo off
chcp 65001 >nul
echo Stopping GoldenShield Python processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1
taskkill /F /IM py.exe /T >nul 2>&1
echo Done. Binance Demo account stays on the exchange — no local MT terminal.
pause
"""

CHECK_BAT = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === GoldenShield folder check (Binance Demo) ===
if not exist main.py (
  echo ERROR: main.py missing
  echo Extract package to this folder then run 00_START.bat
  pause
  exit /b 1
)
if not exist .env (
  echo ERROR: .env missing
  pause
  exit /b 1
)
findstr /B /C:"EXECUTION_BACKEND=binance" .env >nul || echo WARN: EXECUTION_BACKEND should be binance
findstr /B /C:"BINANCE_DEMO_TRADING=true" .env >nul || echo WARN: BINANCE_DEMO_TRADING should be true
findstr /B /C:"MT5_ENABLED=true" .env >nul && echo WARN: MT5_ENABLED=true — should be false
echo OK: project files present
py -c "import sys; print(sys.version)"
pause
"""


def production_env(local: dict[str, str]) -> str:
    """بيئة تشغيل ويندوز: Binance Demo فقط (ليس حقيقي، وليس MT5)."""
    return "\n".join(
        [
            "ENV=production",
            "EXECUTION_MODE=live",
            "EXECUTION_BACKEND=binance",
            "BINANCE_DEMO_TRADING=true",
            "MT5_ENABLED=false",
            "BOT_AUTO_SYNC_MT5=false",
            "MT5_ATTACH_SL_TP=false",
            f"BINANCE_API_KEY={local.get('BINANCE_API_KEY', '')}",
            f"BINANCE_API_SECRET={local.get('BINANCE_API_SECRET', '')}",
            "TELEGRAM_SEND_CYCLE_SIGNALS=true",
            "TELEGRAM_LIVE_SIGNALS=true",
            "TELEGRAM_LIVE_SIGNALS_SECONDS=15",
            "TELEGRAM_SIGNAL_MIN_PERCENT=85",
            "TELEGRAM_SIGNALS_ONLY=false",
            "LOOP_INTERVAL_SECONDS=15",
            "MANUAL_ENTRY_REQUIRED=false",
            "AUTO_ENTRY_MIN_PERCENT=90",
            "IRON_PROTOCOL_ENABLED=true",
            "HIGH_CONVICTION_MODE=false",
            "STANDARD_BONUS_PROFILE=false",
            "MAX_CONCURRENT_POSITIONS=12",
            "TRIAL_MODE=false",
            "TRIAL_JOURNAL_ENABLED=true",
            "BOT_ADMIN_FULL_ACCESS=true",
            f"TELEGRAM_TOKEN={local.get('TELEGRAM_TOKEN', '')}",
            f"TELEGRAM_BOT_USERNAME={local.get('TELEGRAM_BOT_USERNAME', 'GoldenShield_2026_bot')}",
            f"TELEGRAM_CHAT_ID={local.get('TELEGRAM_CHAT_ID', '')}",
            f"TELEGRAM_BACKUP_CHANNEL_ID={local.get('TELEGRAM_BACKUP_CHANNEL_ID', '')}",
            "DB_PATH=storage/db/goldenshield.db",
        ]
    ) + "\n"
