"""
Commander 2 — Z-Score mean reversion on live 1m / 5m klines.
"""

from __future__ import annotations

import asyncio
import math
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from utils.control_state import engines_paused
from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.entry_guards import (
    commit_entry,
    effective_elite_min_percent,
    engine_has_capacity,
    log_entry_skip,
    portfolio_heat_allows,
    portfolio_total_capacity,
    signal_strength_allows,
)
from utils.logger_config import setup_logger
from utils.runtime_env import demo_entry_relax, loop_interval_seconds, recovery_stop_fraction, stop_market_enabled

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
        z_thr = 1.25 if demo_entry_relax() else 2.0
        signal = (
            "MEAN_REVERT_SHORT"
            if z > z_thr
            else "MEAN_REVERT_LONG"
            if z < -z_thr
            else "NEUTRAL"
        )
        spread_bps = self._stream.get_spread_bps(symbol)
        last = self._stream.get_last_close(symbol, "1m")

        payload: Dict[str, Any] = {
            "symbol": symbol,
            "zscore": round(z, 4),
            "signal": signal,
            "frame": "1m/5m",
            "last_close": last,
            "spread_bps": spread_bps,
            "strength_pct": round(min(100.0, abs(z) / 3.0 * 100.0), 1),
            "elite_min_pct": effective_elite_min_percent(),
        }
        now = datetime.now(timezone.utc).isoformat()
        await self._db.save_engine_state_async(self.name, payload, now)
        await self._hub.publish({"type": "engine", "engine": self.name, "data": payload})

        if signal == "NEUTRAL" or last is None:
            return
        if engines_paused():
            return

        strength = min(100.0, abs(z) / 3.0 * 100.0)
        if not signal_strength_allows(strength):
            log_entry_skip(self.name, symbol, f"strength={strength:.1f}<elite={effective_elite_min_percent():.0f}")
            return
        if not await portfolio_total_capacity(self._db):
            log_entry_skip(self.name, symbol, "max_elite_positions")
            return
        if not await engine_has_capacity(self._db, self.name, "GOLD_FLASH_MAX_CONCURRENT", 12):
            log_entry_skip(self.name, symbol, "engine_capacity")
            return

        side = "SELL" if signal.endswith("SHORT") else "BUY"
        qty = 0.002
        ok_heat, heat_reason = await portfolio_heat_allows(self._db, self._client, qty * last)
        if not ok_heat:
            log_entry_skip(self.name, symbol, heat_reason)
            return

        fill = await self._client.place_market_guarded(
            symbol,
            side,
            qty,
            last,
            spread_bps_override=spread_bps,
        )
        if not fill:
            log_entry_skip(self.name, symbol, "order_blocked_spread_or_notional")
            return

        stop_id: Optional[str] = None
        if stop_market_enabled():
            stop_pct = recovery_stop_fraction()
            stop_price = last * (1 - stop_pct) if side == "BUY" else last * (1 + stop_pct)
            stop_side = "SELL" if side == "BUY" else "BUY"
            stop_resp = await self._client.place_stop_market(
                symbol,
                stop_side,
                stop_price,
                qty,
                reference_price=last,
                spread_bps_override=spread_bps,
            )
            if stop_resp:
                stop_id = str(stop_resp.get("clientOrderId") or stop_resp.get("orderId"))
                await self._db.register_protection_order_async(
                    stop_id,
                    symbol,
                    stop_price,
                    str(stop_resp.get("status", "NEW")),
                    now,
                )

        await commit_entry(
            self._db,
            self._hub,
            engine=self.name,
            symbol=symbol,
            side=side,
            quantity=qty,
            entry_price=last,
            stop_order_id=stop_id,
            updated_at=now,
            paper=self._client.paper_trading,
        )
        logger.info("Gold flash %s %s z=%.2f strength=%.1f spread=%s", side, symbol, z, strength, spread_bps)
