#!/usr/bin/env python3
"""
Saqr full health & configuration audit (run from saqr/ root).
Usage: python scripts/full_health_audit.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from utils.runtime_env import bootstrap_environment

bootstrap_environment(ROOT)

REPORT: dict = {"checks": [], "ok": True}


def check(name: str, passed: bool, detail: str) -> None:
    REPORT["checks"].append({"name": name, "passed": passed, "detail": detail})
    if not passed:
        REPORT["ok"] = False
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name}: {detail}")


def audit_env() -> None:
    mode = os.getenv("EXECUTION_MODE", "").strip().lower()
    paper = os.getenv("PAPER_TRADING", "").strip().lower()
    check("EXECUTION_MODE=demo", mode == "demo", f"got EXECUTION_MODE={mode!r}")
    check("PAPER_TRADING=false", paper == "false", f"got PAPER_TRADING={paper!r}")

    root = os.getenv("SAqr_ROOT", "")
    check("SAqr_ROOT set", bool(root), root or "missing")
    check(
        "runtime ROOT matches workspace",
        Path(root).resolve() == ROOT.resolve() if root else False,
        f"SAqr_ROOT={root} workspace={ROOT}",
    )

    base = os.getenv("BINANCE_BASE_URL", "")
    mrest = os.getenv("BINANCE_MARKET_REST_URL", "")
    mws = os.getenv("BINANCE_MARKET_WS_URL", "")
    uws = os.getenv("BINANCE_USER_WS_BASE", "")
    check(
        "BINANCE_BASE_URL testnet",
        "testnet.binancefuture.com" in base.lower(),
        base,
    )
    check(
        "MARKET_REST aligns testnet",
        "testnet.binancefuture.com" in (mrest or base).lower(),
        mrest or "(defaults to base)",
    )
    check(
        "USER_WS testnet",
        "fstream-testnet" in uws.lower() or "testnet" in uws.lower(),
        uws,
    )
    check("MARKET_WS set", bool(mws), mws)

    key = os.getenv("BINANCE_API_KEY", "")
    sec = os.getenv("BINANCE_API_SECRET", "")
    check("API key present", len(key) > 20, f"len={len(key)}")
    check("API secret present", len(sec) > 20, f"len={len(sec)}")
    check(
        "not placeholder key",
        "YOUR_DEMO" not in key,
        "placeholder detected" if "YOUR_DEMO" in key else "ok",
    )


async def audit_binance() -> None:
    from gateway.binance_client import BinanceClient
    from gateway.stream_service import StreamService

    client = BinanceClient()
    check(
        "client paper_trading off for demo",
        not client.paper_trading,
        f"paper={client.paper_trading} mode={client.execution_mode}",
    )
    check("client is_futures", client.is_futures, client.base_url)
    check(
        "market_rest testnet",
        "testnet" in client.market_rest_url.lower() or client.is_futures,
        client.market_rest_url,
    )

    stream = StreamService(hub=None)
    url = stream.build_combined_stream_url()
    check(
        "combined WS URL shape",
        "/stream?streams=" in url and "btcusdt" in url.lower(),
        url[:120] + "...",
    )
    check(
        "WS host binancefuture",
        "binancefuture" in url.lower() or "binance.com" in url.lower(),
        "see full URL in detail",
    )

    await client.start()
    try:
        ping_ok = await client.ping()
        check("REST ping (signed path ready)", ping_ok, "fapi ping" if not client.paper_trading else "skipped")
    except Exception as exc:
        check("REST ping", False, str(exc)[:200])

    if not client.paper_trading and client.api_key:
        try:
            bal = await client.account_balances()
            check("get account/balances", isinstance(bal, list), f"assets={len(bal)}")
        except Exception as exc:
            err = str(exc)
            hint = ""
            if "-2015" in err or "2015" in err:
                hint = " (Invalid API-key — use Futures TESTNET keys)"
            if "-1022" in err or "1022" in err:
                hint = " (Bad signature — check secret / URL match)"
            check("get account/balances", False, err[:180] + hint)

        try:
            rules = await client.get_symbol_rules("BTCUSDT")
            check(
                "exchangeInfo BTCUSDT",
                rules.min_qty > 0,
                f"min_qty={rules.min_qty} min_notional={rules.min_notional}",
            )
        except Exception as exc:
            check("exchangeInfo BTCUSDT", False, str(exc)[:180])

        try:
            kl = await client.fetch_klines("BTCUSDT", "1m", 5)
            check("klines warm", len(kl) >= 1, f"rows={len(kl)}")
        except Exception as exc:
            check("klines warm", False, str(exc)[:180])
    await client.close()


def audit_db_and_modules() -> None:
    from database.db_manager import DatabaseManager
    from engines.gold_flash import GoldFlashEngine
    from engines.momentum import MomentumEngine
    from engines.smc_macro import SmcMacroEngine
    from utils.entry_guards import effective_elite_min_percent

    db = DatabaseManager()
    db.connect()
    path = db.path
    check("DB connect WAL", path.exists() or path.parent.exists(), str(path))
    db.close()

    for cls in (SmcMacroEngine, GoldFlashEngine, MomentumEngine):
        check(f"engine import {cls.name}", True, cls.__name__)

    check("elite min percent", effective_elite_min_percent() > 0, str(effective_elite_min_percent()))


async def audit_ws_public_sample() -> None:
    """One short public WS read (5s max) for stream.binancefuture.com."""
    import websockets

    from gateway.stream_service import StreamService

    stream = StreamService(hub=None)
    url = stream.build_combined_stream_url()

    async def _probe() -> bool:
        try:
            async with websockets.connect(url, ping_interval=20, close_timeout=5) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                return len(msg) > 10
        except Exception:
            return False

    try:
        got = await asyncio.wait_for(_probe(), timeout=12.0)
        check("public market WS recv", got, url[:100])
    except asyncio.TimeoutError:
        check("public market WS recv", False, "timeout (geo/firewall?)")
    except Exception as exc:
        check("public market WS recv", False, str(exc)[:160])


async def main() -> int:
    print("=== Saqr Full Health Audit ===")
    print(f"Workspace: {ROOT}\n")
    audit_env()
    print()
    audit_db_and_modules()
    print()
    await audit_binance()
    print()
    await audit_ws_public_sample()
    print()
    out = ROOT / "logs" / "health_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
    print(f"Report written: {out}")
    print(f"\nOverall: {'OK' if REPORT['ok'] else 'ISSUES FOUND'}")
    return 0 if REPORT["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
