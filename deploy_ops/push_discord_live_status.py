#!/usr/bin/env python3
"""Push one LIVE status embed to Discord (webhook from .env)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    p = Path(raw)
    return p if p.is_dir() else Path(__file__).resolve().parents[1]


def main() -> int:
    root = _root()
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    bridges = root / "bridges" / "discord"
    if str(bridges) not in sys.path:
        sys.path.insert(0, str(bridges))

    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env", override=False)
    except Exception:
        pass

    try:
        from discord_notify import discord_enabled, send_discord
    except Exception as exc:
        print("DISCORD_IMPORT_FAIL", exc)
        return 1

    if not discord_enabled():
        print("DISCORD_DISABLED")
        return 2

    equity = free = 0.0
    exchange_ok = False
    bot_running = False
    demo = False
    source = "unknown"
    try:
        from terminal_app.services import binance_mirror as bm
        from terminal_app.services import bot_bridge as bb

        snap = bm.binance_snapshot(force=True)
        st = bb.status()
        equity = float(st.get("balance") or snap.get("equity") or 0)
        free = float(st.get("free_cash") or snap.get("free_cash") or 0)
        exchange_ok = bool(st.get("exchange_ok"))
        bot_running = bool(st.get("bot_running"))
        demo = bool(st.get("demo"))
        source = str(st.get("balance_source") or "binance")
    except Exception as exc:
        print("STATUS_FAIL", exc)

    live = exchange_ok and bot_running
    color = 0x22C55E if live else 0xEF4444
    ts = datetime.now(timezone.utc).isoformat()
    embed = {
        "title": "GoldenShield ● LIVE" if live else "GoldenShield — degraded",
        "color": color,
        "timestamp": ts,
        "fields": [
            {"name": "System", "value": "● LIVE" if live else "○ CHECK", "inline": True},
            {"name": "Binance", "value": "OK (demo)" if (exchange_ok and demo) else ("OK" if exchange_ok else "DOWN"), "inline": True},
            {"name": "Engine", "value": "RUNNING" if bot_running else "STOPPED", "inline": True},
            {"name": "Total equity (USDT)", "value": f"{equity:,.2f}", "inline": True},
            {"name": "USDT free", "value": f"{free:,.2f}", "inline": True},
            {"name": "Balance source", "value": source, "inline": True},
        ],
        "footer": {"text": "GoldenShield 2.0 · auto status"},
    }
    ok = send_discord("", embeds=[embed])
    print("DISCORD_PUSH_OK" if ok else "DISCORD_PUSH_FAIL")
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
