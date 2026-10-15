#!/usr/bin/env python3
"""Live Binance auth probe — prints masked key presence + USDT balance (no secrets)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    p = Path(raw)
    return p if p.is_dir() else Path(__file__).resolve().parents[1]


def _mask(val: str) -> str:
    v = (val or "").strip()
    if not v:
        return "MISSING"
    if len(v) <= 8:
        return "SET(len=%d)" % len(v)
    return "SET(%s…%s)" % (v[:4], v[-4:])


def main() -> int:
    root = _root()
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env", override=False)
        load_dotenv(root / "goldenshield.env", override=False)
    except Exception:
        pass

    key = (os.getenv("BINANCE_API_KEY") or "").strip()
    secret = (os.getenv("BINANCE_API_SECRET") or "").strip()
    demo = (os.getenv("BINANCE_DEMO_TRADING") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    print("ENV_BINANCE_API_KEY", _mask(key))
    print("ENV_BINANCE_API_SECRET", _mask(secret))
    print("BINANCE_DEMO_TRADING", demo)
    print("EXECUTION_MODE", (os.getenv("EXECUTION_MODE") or "paper").strip())

    if not key or not secret:
        print("RESULT FAIL missing_api_credentials")
        return 1

    try:
        from data.exchange_client import get_exchange

        ex = get_exchange()
        bal = ex.fetch_balance() or {}
        usdt = bal.get("USDT") or bal.get("total", {}).get("USDT")
        free = 0.0
        total = 0.0
        if isinstance(usdt, dict):
            free = float(usdt.get("free") or 0)
            total = float(usdt.get("total") or usdt.get("free") or 0)
        else:
            total = float(usdt or 0)
            free = total
        print("BINANCE_AUTH OK")
        print("USDT_FREE", round(free, 8))
        print("USDT_TOTAL", round(total, 8))
        return 0
    except Exception as exc:
        print("RESULT FAIL", type(exc).__name__, str(exc)[:200])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
