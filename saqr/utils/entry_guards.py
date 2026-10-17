"""
Shared pre-entry guards — elite strength, engine caps, portfolio heat, DB + WS commit.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from database.db_manager import PositionRow
from utils.runtime_env import portfolio_heat_cap_fraction

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager


def elite_min_percent(default: float = 85.0) -> float:
    try:
        return float(os.getenv("ELITE_MIN_PERCENT", str(default)))
    except ValueError:
        return default


def max_elite_concurrent(default: int = 20) -> int:
    try:
        return int(os.getenv("MAX_ELITE_CONCURRENT_POSITIONS", str(default)))
    except ValueError:
        return default


def signal_strength_allows(strength_pct: float) -> bool:
    """Entry only when model strength meets ELITE_MIN_PERCENT (signals may still broadcast below)."""
    return strength_pct >= elite_min_percent()


def engine_max_concurrent(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, str(default)))
    except ValueError:
        return default


async def engine_has_capacity(db: "DatabaseManager", engine: str, env_key: str, default: int) -> bool:
    limit = engine_max_concurrent(env_key, default)
    positions = await db.list_positions_async()
    open_for = sum(1 for p in positions if p.engine == engine)
    return open_for < limit


async def portfolio_total_capacity(db: "DatabaseManager") -> bool:
    total = len(await db.list_positions_async())
    return total < max_elite_concurrent()


async def portfolio_heat_allows(
    db: "DatabaseManager",
    client: "BinanceClient",
    additional_notional: float,
) -> Tuple[bool, str]:
    cap = portfolio_heat_cap_fraction(0.07)
    if cap <= 0:
        return False, "portfolio_heat_cap_disabled"
    positions = await db.list_positions_async()
    open_notional = sum(max(0.0, p.quantity * p.entry_price) for p in positions)
    balances = await client.account_balances()
    equity = 0.0
    for b in balances:
        if str(b.get("asset", "")).upper() == "USDT":
            equity += float(b.get("free", 0)) + float(b.get("locked", 0))
    if equity <= 0:
        equity = 10_000.0
    projected = (open_notional + additional_notional) / equity
    if projected > cap:
        return False, f"portfolio_heat={projected:.4f}>{cap:.4f}"
    return True, "ok"


async def commit_entry(
    db: "DatabaseManager",
    hub: "ConnectionManager",
    *,
    engine: str,
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    stop_order_id: Optional[str],
    updated_at: str,
    paper: bool,
) -> None:
    await db.upsert_position_async(
        PositionRow(
            symbol=symbol.upper(),
            side=side.upper(),
            quantity=quantity,
            entry_price=entry_price,
            stop_order_id=stop_order_id,
            engine=engine,
            updated_at=updated_at,
        )
    )
    payload: Dict[str, Any] = {
        "type": "entry",
        "engine": engine,
        "symbol": symbol.upper(),
        "side": side.upper(),
        "quantity": quantity,
        "entry_price": entry_price,
        "stop_order_id": stop_order_id,
        "paper": paper,
        "updated_at": updated_at,
    }
    await hub.publish(payload)
