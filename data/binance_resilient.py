"""Resilient Binance Demo balance fetch — multiple paths, no external proxy required."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any


def _root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    p = Path(raw)
    if p.is_dir():
        return p
    return Path(__file__).resolve().parents[1]


def _bootstrap() -> Path:
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
    return root


def _is_geo(msg: str) -> bool:
    low = (msg or "").lower()
    return "451" in msg or "restricted location" in low or "service unavailable from a restricted" in low


def path_ccxt_fetch_balance() -> dict[str, Any]:
    from data.exchange_client import get_exchange, reset_exchange

    reset_exchange()
    ex = get_exchange()
    bal = ex.fetch_balance() or {}
    usdt = bal.get("USDT") or {}
    free = float((usdt.get("free") if isinstance(usdt, dict) else usdt) or 0)
    total = float((usdt.get("total") if isinstance(usdt, dict) else free) or free)
    return {
        "path": "ccxt_fetch_balance",
        "ok": True,
        "free": free,
        "total": total,
        "error": None,
    }


def path_ccxt_balance_no_load_markets() -> dict[str, Any]:
    os.environ["BINANCE_SKIP_LOAD_MARKETS"] = "true"
    return path_ccxt_fetch_balance()


def path_disk_snapshot() -> dict[str, Any]:
    root = _bootstrap()
    path = root / "storage" / "runtime" / "binance_snapshot.json"
    if not path.is_file():
        return {"path": "disk_snapshot", "ok": False, "error": "missing file"}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("ok"):
        return {"path": "disk_snapshot", "ok": False, "error": "invalid snapshot"}
    return {
        "path": "disk_snapshot",
        "ok": True,
        "equity": float(data.get("equity") or 0),
        "free": float(data.get("free_cash") or 0),
        "error": None,
    }


def path_zero_copy_account() -> dict[str, Any]:
    _bootstrap()
    try:
        from data_highway.zero_copy_cache import account_state

        acc = account_state()
        if acc.get("ok") and acc.get("equity") is not None:
            return {
                "path": "zero_copy_account",
                "ok": True,
                "equity": float(acc.get("equity") or 0),
                "free": float(acc.get("free_cash") or 0),
                "error": None,
            }
    except Exception as exc:
        return {"path": "zero_copy_account", "ok": False, "error": str(exc)[:120]}
    return {"path": "zero_copy_account", "ok": False, "error": "empty"}


def probe_all_paths() -> list[dict[str, Any]]:
    _bootstrap()
    results: list[dict[str, Any]] = []
    for fn in (
        path_ccxt_balance_no_load_markets,
        path_ccxt_fetch_balance,
        path_disk_snapshot,
        path_zero_copy_account,
    ):
        try:
            results.append(fn())
        except Exception as exc:
            results.append(
                {
                    "path": getattr(fn, "__name__", "unknown"),
                    "ok": False,
                    "error": str(exc)[:200],
                    "geo": _is_geo(str(exc)),
                }
            )
        time.sleep(0.2)
    return results


def main() -> int:
    results = probe_all_paths()
    any_ok = False
    for row in results:
        tag = "OK" if row.get("ok") else "FAIL"
        extra = ""
        if row.get("free") is not None:
            extra = f" free={row.get('free')}"
        if row.get("equity") is not None:
            extra = f" equity={row.get('equity')}"
        if row.get("total") is not None:
            extra = f" total={row.get('total')}"
        err = row.get("error")
        print(f"{tag}\t{row.get('path')}{extra}" + (f"\t{err}" if err else ""))
        if row.get("ok"):
            any_ok = True
    return 0 if any_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
