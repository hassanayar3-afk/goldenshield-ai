"""حزمة تشغيل Windows — Binance Demo فقط."""

from __future__ import annotations


def production_env(local: dict[str, str]) -> str:
    """بيئة تشغيل ويندوز: Binance Demo فقط (ليس حساب حقيقي)."""
    return "\n".join(
        [
            "ENV=production",
            "EXECUTION_MODE=live",
            "EXECUTION_BACKEND=binance",
            "BINANCE_DEMO_TRADING=true",
            f"BINANCE_API_KEY={local.get('BINANCE_API_KEY', '')}",
            f"BINANCE_API_SECRET={local.get('BINANCE_API_SECRET', '')}",
            "TELEGRAM_SEND_CYCLE_SIGNALS=true",
            "TELEGRAM_LIVE_SIGNALS=true",
            "TELEGRAM_LIVE_SIGNALS_SECONDS=4",
            "TELEGRAM_LIVE_POSITIONS_SECONDS=3",
            "NO_SLEEP_MODE=true",
            "TELEGRAM_SIGNAL_MIN_PERCENT=85",
            "TELEGRAM_SIGNALS_ONLY=false",
            "LOOP_INTERVAL_SECONDS=4",
            "MANUAL_ENTRY_REQUIRED=false",
            "AUTO_ENTRY_MIN_PERCENT=90",
            "IRON_PROTOCOL_ENABLED=true",
            "HIGH_CONVICTION_MODE=false",
            "STANDARD_BONUS_PROFILE=false",
            "MAX_CONCURRENT_POSITIONS=12",
            "TRIAL_MODE=false",
            "TRIAL_JOURNAL_ENABLED=true",
            "BOT_ADMIN_FULL_ACCESS=true",
            "SHADOW_STRESS_ENABLED=true",
            "SHADOW_WATCH_MINUTES=15",
            "SHADOW_MIN_PERCENT=90",
            "TRAP_FAIL_STREAK=3",
            "TRAP_COOLDOWN_MINUTES=60",
            "ORDERBOOK_IMBALANCE_GATE_ENABLED=true",
            "ORDERBOOK_IMBALANCE_MIN=0.15",
            "ADAPTIVE_WEIGHTS_ENABLED=true",
            "ADAPTIVE_WEIGHT_MAX_DELTA=0.20",
            "MOMENTUM_PREEMPTIVE_EXIT_ENABLED=false",
            "RISK_COMMITTEE_ENABLED=true",
            "RISK_COMMITTEE_LLM_ENABLED=false",
            "RISK_COMMITTEE_FAIL_CLOSED=false",
            "MACRO_FLOW_GATE_ENABLED=true",
            f"TELEGRAM_TOKEN={local.get('TELEGRAM_TOKEN', '')}",
            f"TELEGRAM_BOT_USERNAME={local.get('TELEGRAM_BOT_USERNAME', 'GoldenShield_2026_bot')}",
            f"TELEGRAM_CHAT_ID={local.get('TELEGRAM_CHAT_ID', '')}",
            f"TELEGRAM_BACKUP_CHANNEL_ID={local.get('TELEGRAM_BACKUP_CHANNEL_ID', '')}",
            f"DISCORD_NOTIFY_ENABLED={local.get('DISCORD_NOTIFY_ENABLED', 'true')}",
            f"DISCORD_WEBHOOK_URL={local.get('DISCORD_WEBHOOK_URL', '')}",
            f"DISCORD_BOT_TOKEN={local.get('DISCORD_BOT_TOKEN', '')}",
            f"DISCORD_CHANNEL_ID={local.get('DISCORD_CHANNEL_ID', '')}",
            "DB_PATH=storage/db/goldenshield.db",
        ]
    ) + "\n"


START_BAT = r"""@echo off
cd /d "%~dp0"
echo === GoldenShield Binance Demo - auto restart ===
:loop
py -u main.py
echo.
echo Bot exited - restart in 5s
timeout /t 5 /nobreak >nul
goto loop
"""

STOP_BAT = r"""@echo off
cd /d "%~dp0"
echo Stopping GoldenShield Python processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1
taskkill /F /IM py.exe /T >nul 2>&1
echo Done.
pause
"""

CHECK_BAT = r"""@echo off
cd /d "%~dp0"
echo === GoldenShield folder check ===
if not exist main.py (
  echo ERROR: main.py missing
  pause
  exit /b 1
)
if not exist .env (
  echo ERROR: .env missing
  pause
  exit /b 1
)
echo OK: project files present
py -c "import sys; print(sys.version)"
pause
"""
