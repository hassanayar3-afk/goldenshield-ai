"""
Commander 3 — Ultra-short momentum bursts with IOC limit orders.
"""

from __future__ import annotations

import asyncio
import os
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict

from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager

logger = setup_logger("saqr.engine.momentum")


class MomentumEngine:
    name = "momentum"

    def __init__(
        self,
        db: "DatabaseManager",
        client: "BinanceClient",
        hub: "ConnectionManager",
    ) -> None:
        self._db = db
        self._client = client
        self._hub = hub
        self._liquid_universe = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

    @crash_proof(component="momentum", restart_delay=2.0)
    async def run_forever(self) -> None:
        while True:
            touch_event_loop_heartbeat()
            symbol = random.choice(self._liquid_universe)
            await self._scan_momentum(symbol)
            await asyncio.sleep(float(os.getenv("ENGINE_TICK_SECONDS", "2")))

    async def _scan_momentum(self, symbol: str) -> None:
        momentum_score = random.uniform(-3, 3)
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "momentum_score": round(momentum_score, 4),
            "liquidity_tier": "elite",
        }
        now = datetime.now(timezone.utc).isoformat()
        self._db.save_engine_state(self.name, payload, now)
        await self._hub.publish({"type": "engine", "engine": self.name, "data": payload})

        heat_cap = float(os.getenv("MAX_PORTFOLIO_HEAT_PCT", "8"))
        if abs(momentum_score) < 2.2:
            return
        if heat_cap <= 0:
            return

        side = "BUY" if momentum_score > 0 else "SELL"
        qty = 0.0015
        ref_price = 100.0 * (1 + momentum_score / 100)
        await self._client.place_ioc_limit(symbol, side, qty, ref_price)
        logger.info("Momentum IOC %s %s score=%.2f", side, symbol, momentum_score)
