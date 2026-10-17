"""
Binance position & balance sync — local DB is reconciled against exchange truth.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List

from database.db_manager import DatabaseManager, PositionRow
from utils.control_state import engines_paused
from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger

if TYPE_CHECKING:
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager

logger = setup_logger("saqr.sync")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncService:
    def __init__(
        self,
        db: DatabaseManager,
        client: "BinanceClient",
        hub: "ConnectionManager",
    ) -> None:
        self._db = db
        self._client = client
        self._hub = hub
        self._running = False
        self._last_snapshot: Dict[str, Any] = {}

    @property
    def last_snapshot(self) -> Dict[str, Any]:
        return dict(self._last_snapshot)

    def interval_seconds(self) -> float:
        try:
            return float(os.getenv("LOOP_INTERVAL_SECONDS", "4"))
        except ValueError:
            return 5.0

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
        snapshot = {
            "type": "sync",
            "balances": balances,
            "positions": [p.__dict__ for p in positions],
            "open_orders": open_orders,
            "paper": self._client.paper_trading,
            "synced_at": now,
            "wins": wins,
            "losses": losses,
            "engines_paused": engines_paused(),
        }
        self._last_snapshot = snapshot
        await self._hub.publish(snapshot)
        return snapshot

    def stop(self) -> None:
        self._running = False

    def restore_paper_position(self, row: PositionRow) -> None:
        """Engines may persist intent; sync keeps DB as operational mirror."""
        self._db.upsert_position(row)
