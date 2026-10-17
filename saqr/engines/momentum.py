"""
Commander 3 — Live 1m momentum bursts with guarded IOC limit orders.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from utils.control_state import engines_paused
from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger
from utils.entry_guards import (
    commit_entry,
    engine_has_capacity,
    portfolio_heat_allows,
    portfolio_total_capacity,
    signal_strength_allows,
)
from utils.runtime_env import loop_interval_seconds

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager
    from gateway.stream_service import StreamService

logger = setup_logger("saqr.engine.momentum")


class MomentumEngine:
    name = "momentum"

    def __init__(
        self,
        db: "DatabaseManager",
        client: "BinanceClient",
        hub: "ConnectionManager",
        stream: "StreamService",
    ) -> None:
        self._db = db
        self._client = client
        self._hub = hub
        self._stream = stream
        self._liquid_universe = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
        self._cursor = 0

    def _momentum_score(self, closes: List[float], lookback: int = 12) -> float:
        if len(closes) <= lookback:
            return 0.0
        base = closes[-lookback - 1]
        last = closes[-1]
        if base <= 0:
            return 0.0
        pct = ((last - base) / base) * 100.0
        return pct

    @crash_proof(component="momentum", restart_delay=2.0)
    async def run_forever(self) -> None:
        while True:
            touch_event_loop_heartbeat()
            symbol = self._liquid_universe[self._cursor % len(self._liquid_universe)]
            self._cursor += 1
            await self._scan_momentum(symbol)
            await asyncio.sleep(loop_interval_seconds(4.0))

    async def _scan_momentum(self, symbol: str) -> None:
        closes = self._stream.get_closes(symbol, "1m", 120)
        last = self._stream.get_last_close(symbol, "1m")
        spread_bps = self._stream.get_spread_bps(symbol)
        momentum_score = self._momentum_score(closes)

        payload: Dict[str, Any] = {
            "symbol": symbol,
            "momentum_score": round(momentum_score, 4),
            "liquidity_tier": "elite",
            "last_close": last,
            "spread_bps": spread_bps,
            "strength_pct": round(min(100.0, abs(momentum_score) / 1.0 * 100.0), 1),
            "elite_min_pct": float(os.getenv("ELITE_MIN_PERCENT", "85")),
        }
        now = datetime.now(timezone.utc).isoformat()
        await self._db.save_engine_state_async(self.name, payload, now)
        await self._hub.publish({"type": "engine", "engine": self.name, "data": payload})

        if abs(momentum_score) < 0.35 or last is None:
            return
        if engines_paused():
            return

        strength = min(100.0, abs(momentum_score) / 1.0 * 100.0)
        if not signal_strength_allows(strength):
            return
        if not await portfolio_total_capacity(self._db):
            return
        if not await engine_has_capacity(self._db, self.name, "MICRO_MOMENTUM_MAX_CONCURRENT", 5):
            return

        side = "BUY" if momentum_score > 0 else "SELL"
        qty = 0.0015
        ok_heat, _ = await portfolio_heat_allows(self._db, self._client, qty * last)
        if not ok_heat:
            return

        fill = await self._client.place_ioc_limit(
            symbol,
            side,
            qty,
            last,
            spread_bps_override=spread_bps,
        )
        if not fill:
            return

        await commit_entry(
            self._db,
            self._hub,
            engine=self.name,
            symbol=symbol,
            side=side,
            quantity=qty,
            entry_price=last,
            stop_order_id=None,
            updated_at=now,
            paper=self._client.paper_trading,
        )
        logger.info("Momentum IOC %s %s score=%.2f strength=%.1f", side, symbol, momentum_score, strength)
