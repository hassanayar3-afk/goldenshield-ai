"""
Optional paper demo entries on boot (local validation only).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.entry_guards import commit_entry, log_entry_skip
from utils.logger_config import setup_logger
from utils.runtime_env import demo_entry_relax, demo_seed_trades

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager
    from gateway.stream_service import StreamService

logger = setup_logger("saqr.demo_seed")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_demo_seed_if_enabled(
    db: "DatabaseManager",
    client: "BinanceClient",
    stream: "StreamService",
    hub: "ConnectionManager",
) -> int:
    try:
        mode = os.getenv("EXECUTION_MODE", "paper").strip().lower()
        if mode in ("demo", "live"):
            return 0
        if not demo_entry_relax():
            return 0
        target = demo_seed_trades(0)
        if target <= 0:
            return 0
        existing = await db.list_positions_async()
        if existing:
            log_entry_skip("demo_seed", "—", "positions_already_open")
            return 0

        plan = [
            ("gold_flash", "BTCUSDT", "BUY", 0.002),
            ("gold_flash", "SOLUSDT", "SELL", 0.002),
            ("smc_macro", "BTCUSDT", "BUY", 0.001),
            ("smc_macro", "ETHUSDT", "BUY", 0.001),
            ("momentum", "BNBUSDT", "BUY", 0.0015),
            ("momentum", "ETHUSDT", "SELL", 0.0015),
            ("momentum", "SOLUSDT", "BUY", 0.0015),
            ("gold_flash", "BTCUSDT", "SELL", 0.002),
            ("smc_macro", "ETHUSDT", "BUY", 0.001),
            ("momentum", "BTCUSDT", "BUY", 0.0015),
        ][: min(target, 10)]

        created = 0
        now = _utc_now()
        for engine, symbol, side, qty in plan:
            last = stream.get_last_close(symbol, "1m") or stream.get_last_close(symbol, "5m")
            if last is None:
                log_entry_skip("demo_seed", symbol, "no_price")
                continue
            fill = await client.place_market_guarded(
                symbol,
                side,
                qty,
                last,
                spread_bps_override=stream.get_spread_bps(symbol),
            )
            if not fill:
                log_entry_skip("demo_seed", symbol, "validate_order_blocked")
                continue
            await commit_entry(
                db,
                hub,
                engine=engine,
                symbol=symbol,
                side=side,
                quantity=qty,
                entry_price=last,
                stop_order_id=None,
                updated_at=now,
                paper=client.paper_trading,
            )
            created += 1
        logger.info("Demo seed created %s paper positions (target=%s)", created, target)
        return created
    except Exception as exc:
        logger.error("Demo seed failed: %s", exc)
        return 0
