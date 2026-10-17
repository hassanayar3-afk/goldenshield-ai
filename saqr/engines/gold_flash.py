"""
Commander 2 — Z-Score mean reversion on live 1m / 5m klines.
"""

from __future__ import annotations

import asyncio
import math
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List

from utils.control_state import engines_paused
from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger
from utils.runtime_env import loop_interval_seconds

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager
    from gateway.stream_service import StreamService

logger = setup_logger("saqr.engine.gold_flash")


class GoldFlashEngine:
    name = "gold_flash"

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
            await asyncio.sleep(loop_interval_seconds(4.0))

    async def _tick_symbol(self, symbol: str) -> None:
        closes_1m = self._stream.get_closes(symbol, "1m", 200)
        closes_5m = self._stream.get_closes(symbol, "5m", 200)
        merged = closes_5m if len(closes_5m) >= 20 else closes_1m
        z = self._zscore(merged)
        signal = "MEAN_REVERT_SHORT" if z > 2.0 else "MEAN_REVERT_LONG" if z < -2.0 else "NEUTRAL"
        spread_bps = self._stream.get_spread_bps(symbol)
        last = self._stream.get_last_close(symbol, "1m")

        payload: Dict[str, Any] = {
            "symbol": symbol,
            "zscore": round(z, 4),
            "signal": signal,
            "frame": "1m/5m",
            "last_close": last,
            "spread_bps": spread_bps,
        }
        now = datetime.now(timezone.utc).isoformat()
        await self._db.save_engine_state_async(self.name, payload, now)
        await self._hub.publish({"type": "engine", "engine": self.name, "data": payload})

        if signal == "NEUTRAL" or last is None:
            return
        if engines_paused():
            return

        try:
            max_pos = int(os.getenv("GOLD_FLASH_MAX_CONCURRENT", "12"))
        except ValueError:
            max_pos = 12
        open_for_engine = sum(1 for p in await self._db.list_positions_async() if p.engine == self.name)
        if open_for_engine >= max_pos:
            return

        side = "SELL" if signal.endswith("SHORT") else "BUY"
        qty = 0.002
        await self._client.place_market_guarded(
            symbol,
            side,
            qty,
            last,
            spread_bps_override=spread_bps,
        )
        logger.info("Gold flash %s %s z=%.2f spread=%s", side, symbol, z, spread_bps)
