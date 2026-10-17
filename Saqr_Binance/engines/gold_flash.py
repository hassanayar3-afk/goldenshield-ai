"""
Commander 2 — Z-Score mean reversion scalper on 1m / 5m microstructure.
"""

from __future__ import annotations

import asyncio
import math
import os
import random
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Deque, Dict, List

from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager

logger = setup_logger("saqr.engine.gold_flash")


class GoldFlashEngine:
    name = "gold_flash"

    def __init__(
        self,
        db: "DatabaseManager",
        client: "BinanceClient",
        hub: "ConnectionManager",
    ) -> None:
        self._db = db
        self._client = client
        self._hub = hub
        self._price_windows: Dict[str, Deque[float]] = {}

    def _window(self, symbol: str) -> Deque[float]:
        if symbol not in self._price_windows:
            self._price_windows[symbol] = deque(maxlen=1000)
        return self._price_windows[symbol]

    def _zscore(self, samples: List[float]) -> float:
        if len(samples) < 20:
            return 0.0
        mean = sum(samples) / len(samples)
        var = sum((x - mean) ** 2 for x in samples) / len(samples)
        std = math.sqrt(var) if var > 0 else 1e-9
        return (samples[-1] - mean) / std

    @crash_proof(component="gold_flash", restart_delay=2.0)
    async def run_forever(self) -> None:
        symbols = ["BTCUSDT", "SOLUSDT"]
        while True:
            touch_event_loop_heartbeat()
            for symbol in symbols:
                await self._tick_symbol(symbol)
            await asyncio.sleep(float(os.getenv("ENGINE_TICK_SECONDS", "2")))

    async def _tick_symbol(self, symbol: str) -> None:
        window = self._window(symbol)
        # Simulated 1m/5m micro price; swap for WS kline feed.
        window.append(100 + random.gauss(0, 0.6))
        z = self._zscore(list(window))
        signal = "MEAN_REVERT_SHORT" if z > 2.0 else "MEAN_REVERT_LONG" if z < -2.0 else "NEUTRAL"

        payload = {"symbol": symbol, "zscore": round(z, 4), "signal": signal, "frame": "1m/5m"}
        now = datetime.now(timezone.utc).isoformat()
        self._db.save_engine_state(self.name, payload, now)
        await self._hub.publish({"type": "engine", "engine": self.name, "data": payload})

        max_spread_bps = float(os.getenv("MAX_SPREAD_BPS", "15"))
        spread_bps = random.uniform(2, 12)
        if spread_bps > max_spread_bps:
            logger.info("Gold flash skip %s — spread %.2f bps", symbol, spread_bps)
            return

        if signal == "NEUTRAL":
            return

        side = "SELL" if signal.endswith("SHORT") else "BUY"
        qty = 0.002
        await self._client.place_market_order(symbol, side, qty)
        logger.info("Gold flash %s %s z=%.2f", side, symbol, z)
