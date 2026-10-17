"""Mirror bot risk/balance into storage/runtime for Mobile API (451 / REST fallback)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", r"C:\GoldenShield_Binance"))
RUNTIME = ROOT / "storage" / "runtime"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def push_runtime_mirror(risk_state: Any | None = None) -> None:
    """Write heartbeat + balance mirror without raising into the bot loop."""
    try:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        balance = 0.0
        session_start = 0.0
        daily_profit = 0.0
        daily_loss = 0.0
        kill = False
        if risk_state is not None:
            balance = float(getattr(risk_state, "current_balance", 0) or 0)
            session_start = float(getattr(risk_state, "session_start_balance", 0) or balance)
            daily_profit = float(getattr(risk_state, "daily_profit", 0) or 0)
            daily_loss = float(getattr(risk_state, "daily_loss", 0) or 0)
            kill = bool(getattr(risk_state, "kill_switch_active", False))

        payload = {
            "ts": _utc(),
            "service": "bot-cycle",
            "equity": round(balance, 8),
            "session_start_equity": round(session_start, 8),
            "session_pnl": round(balance - session_start, 8),
            "daily_profit": round(daily_profit, 8),
            "daily_loss": round(daily_loss, 8),
            "daily_net": round(daily_profit + daily_loss, 8),
            "kill_switch_active": kill,
            "source": "bot_risk_state",
        }
        (RUNTIME / "balance_mirror.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (RUNTIME / "heartbeat.json").write_text(
            json.dumps(
                {"ts": payload["ts"], "service": "bot-main", "balance": payload["equity"]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (RUNTIME / "gs_runtime_status.json").write_text(
            json.dumps({"bot_running": True, **payload}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
