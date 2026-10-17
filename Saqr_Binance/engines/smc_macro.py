"""
Commander 1 — SMC macro structure on 1H / 4H horizons (async, non-blocking).
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict

from database.db_manager import PositionRow
from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager

logger = setup_logger("saqr.engine.smc")


class SmcMacroEngine:
    name = "smc_macro"

    def __init__(
        self,
        db: "DatabaseManager",
        client: "BinanceClient",
        hub: "ConnectionManager",
    ) -> None:
        self._db = db
        self._client = client
        self._hub = hub
        self._symbols = ["BTCUSDT", "ETHUSDT"]

    def _tick_seconds(self) -> float:
        try:
            return float(os.getenv("ENGINE_TICK_SECONDS", "2"))
        except ValueError:
            return 2.0

    @crash_proof(component="smc_macro", restart_delay=3.0)
    async def run_forever(self) -> None:
        while True:
            touch_event_loop_heartbeat()
            for symbol in self._symbols:
                await self._evaluate_symbol(symbol)
            await asyncio.sleep(self._tick_seconds())

    async def _evaluate_symbol(self, symbol: str) -> None:
        """
        Lightweight SMC placeholder: bias from synthetic 1H/4H structure score.
        Production hook: replace with real OHLCV + order-block detection.
        """
        score_1h = random.uniform(-1, 1)
        score_4h = random.uniform(-1, 1)
        bias = "LONG" if score_1h + score_4h > 0.8 else "FLAT"
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "bias": bias,
            "score_1h": round(score_1h, 4),
            "score_4h": round(score_4h, 4),
        }
        now = datetime.now(timezone.utc).isoformat()
        self._db.save_engine_state(self.name, payload, now)
        await self._hub.publish({"type": "engine", "engine": self.name, "data": payload})

        if bias != "LONG":
            return

        qty = 0.001
        stop_pct = 0.015
        entry = 65000.0 if symbol == "BTCUSDT" else 3200.0
        stop_price = entry * (1 - stop_pct)

        if os.getenv("DEFAULT_STOP_MARKET", "true").lower() in ("1", "true", "yes"):
            stop_side = "SELL"
            stop_resp = await self._client.place_stop_market(symbol, stop_side, stop_price, qty)
            stop_id = str(stop_resp.get("clientOrderId") or stop_resp.get("orderId"))
        else:
            stop_id = None

        self._db.upsert_position(
            PositionRow(
                symbol=symbol,
                side="BUY",
                quantity=qty,
                entry_price=entry,
                stop_order_id=stop_id,
                engine=self.name,
                updated_at=now,
            )
        )
        logger.info("SMC macro signal %s bias=%s stop=%s", symbol, bias, stop_price)
