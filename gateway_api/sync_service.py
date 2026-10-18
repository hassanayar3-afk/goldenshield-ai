"""
Binance position & balance sync — local DB is reconciled against exchange truth.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List

from data_highway.sqlite_store import DatabaseManager, PositionRow
from risk_sentinel.control_state import engines_paused
from risk_sentinel.crash_watchdog import crash_proof, touch_event_loop_heartbeat
from data_highway.logging_config import setup_logger
from data_highway.runtime_env import loop_interval_seconds, no_sleep_mode

if TYPE_CHECKING:
    from gateway_api.binance_client import BinanceClient
    from gateway_api.connection_manager import ConnectionManager
    from risk_sentinel.circuit_breaker import GlobalCircuitBreaker
    from gateway_api.stream_service import StreamService

from risk_sentinel.pnl import mark_price_for_symbol, unrealized_pct, unrealized_pnl

logger = setup_logger("saqr.sync")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncService:
    def __init__(
        self,
        db: DatabaseManager,
        client: "BinanceClient",
        hub: "ConnectionManager",
        stream: "StreamService | None" = None,
        circuit_breaker: "GlobalCircuitBreaker | None" = None,
    ) -> None:
        self._db = db
        self._client = client
        self._hub = hub
        self._stream = stream
        self._circuit = circuit_breaker
        self._running = False
        self._last_snapshot: Dict[str, Any] = {}

    @property
    def last_snapshot(self) -> Dict[str, Any]:
        return dict(self._last_snapshot)

    def set_circuit_breaker(self, breaker: "GlobalCircuitBreaker") -> None:
        self._circuit = breaker

    def interval_seconds(self) -> float:
        if no_sleep_mode():
            return 1.0
        return loop_interval_seconds(4.0)

    @crash_proof(component="sync_service", restart_delay=2.0)
    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            touch_event_loop_heartbeat()
            try:
                await self.sync_once()
            except Exception as exc:
                logger.error("Sync iteration failed: %s", exc)
            await asyncio.sleep(self.interval_seconds())

    async def sync_once(self) -> Dict[str, Any]:
        balances_raw = await self._client.account_balances()
        balances: List[Dict[str, Any]] = []
        now = _utc_now()
        for b in balances_raw:
            free = float(b.get("free", 0))
            locked = float(b.get("locked", 0))
            if free + locked <= 0:
                continue
            asset = str(b.get("asset", ""))
            await self._db.run_dao(self._db.upsert_balance, asset, free, locked, now)
            balances.append({"asset": asset, "free": free, "locked": locked})

        positions = await self._db.list_positions_async()
        open_orders = await self._client.open_orders()

        wins, losses = await self._db.closed_trade_counts_async()
        enriched: List[Dict[str, Any]] = []
        total_unrealized = 0.0
        for p in positions:
            mark = mark_price_for_symbol(self._stream, p.symbol, p.entry_price)
            upnl = unrealized_pnl(p, mark)
            upct = unrealized_pct(p, mark)
            total_unrealized += upnl
            row = dict(p.__dict__)
            row["mark_price"] = mark
            row["unrealized_pnl"] = round(upnl, 6)
            row["unrealized_pct"] = round(upct, 4)
            enriched.append(row)

        usdt_equity = 0.0
        for b in balances:
            if str(b.get("asset", "")).upper() == "USDT":
                usdt_equity = float(b.get("free", 0)) + float(b.get("locked", 0))
        if usdt_equity <= 0:
            usdt_equity = 10_000.0
        unrealized_pct_portfolio = (total_unrealized / usdt_equity) * 100.0

        positions_by_engine: Dict[str, Dict[str, Any]] = {}
        for row in enriched:
            positions_by_engine[str(row.get("engine", ""))] = row

        snapshot = {
            "type": "sync",
            "balances": balances,
            "positions": enriched,
            "positions_by_engine": positions_by_engine,
            "open_orders": open_orders,
            "paper": self._client.paper_trading,
            "synced_at": now,
            "wins": wins,
            "losses": losses,
            "engines_paused": engines_paused(),
            "total_unrealized_pnl": round(total_unrealized, 6),
            "unrealized_pnl_pct": round(unrealized_pct_portfolio, 4),
            "circuit_breaker_tripped": self._circuit.tripped if self._circuit else False,
        }
        self._last_snapshot = snapshot
        await self._hub.publish(snapshot)
        if self._circuit is not None:
            await self._circuit.evaluate(snapshot)
        return snapshot

    def stop(self) -> None:
        self._running = False

    def restore_paper_position(self, row: PositionRow) -> None:
        """Engines may persist intent; sync keeps DB as operational mirror."""
        self._db.upsert_position(row)
