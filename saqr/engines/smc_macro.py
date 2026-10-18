"""
Commander 1 — SMC macro structure on live 1H / 4H klines (async, non-blocking).
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
    effective_elite_min_percent,
    engine_has_capacity,
    log_entry_skip,
    portfolio_heat_allows,
    portfolio_total_capacity,
    signal_strength_allows,
)
from utils.runtime_env import demo_entry_relax, loop_interval_seconds, stop_market_enabled

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager
    from gateway.stream_service import StreamService

logger = setup_logger("saqr.engine.smc")


def _sma(closes: List[float], period: int) -> Optional[float]:
    if len(closes) < period:
        return None
    window = closes[-period:]
    return sum(window) / len(window)


class SmcMacroEngine:
    name = "smc_macro"

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
        self._symbols = ["BTCUSDT", "ETHUSDT"]

    def _tick_seconds(self) -> float:
        return loop_interval_seconds(4.0)

    def _max_concurrent(self) -> int:
        try:
            return int(os.getenv("SMC_MAX_CONCURRENT", "4"))
        except ValueError:
            return 4

    @crash_proof(component="smc_macro", restart_delay=3.0)
    async def run_forever(self) -> None:
        while True:
            touch_event_loop_heartbeat()
            for symbol in self._symbols:
                await self._evaluate_symbol(symbol)
            await asyncio.sleep(self._tick_seconds())

    async def _evaluate_symbol(self, symbol: str) -> None:
        closes_1h = self._stream.get_closes(symbol, "1h", 120)
        closes_4h = self._stream.get_closes(symbol, "4h", 120)
        entry = self._stream.get_last_close(symbol, "1h") or self._stream.get_last_close(symbol, "1m")
        spread_bps = self._stream.get_spread_bps(symbol)

        sma20_1h = _sma(closes_1h, 20)
        sma20_4h = _sma(closes_4h, 20)
        score_1h = 0.0 if sma20_1h is None or entry is None else (entry - sma20_1h) / sma20_1h
        score_4h = 0.0 if sma20_4h is None or entry is None else (entry - sma20_4h) / sma20_4h
        if demo_entry_relax():
            bias = "LONG" if score_1h > 0.0003 and score_4h > 0.0001 else "FLAT"
        else:
            bias = "LONG" if score_1h > 0.002 and score_4h > 0.001 else "FLAT"

        payload: Dict[str, Any] = {
            "symbol": symbol,
            "bias": bias,
            "score_1h": round(score_1h, 6),
            "score_4h": round(score_4h, 6),
            "entry": entry,
            "spread_bps": spread_bps,
            "frames": "1H/4H",
            "strength_pct": round(
                min(100.0, max(0.0, (score_1h / 0.002) * 45.0 + (score_4h / 0.001) * 45.0)),
                1,
            ),
            "elite_min_pct": effective_elite_min_percent(),
        }
        now = datetime.now(timezone.utc).isoformat()
        await self._db.save_engine_state_async(self.name, payload, now)
        await self._hub.publish({"type": "engine", "engine": self.name, "data": payload})

        if bias != "LONG" or entry is None:
            return
        if engines_paused():
            return

        strength = min(
            100.0,
            max(0.0, (score_1h / 0.002) * 45.0 + (score_4h / 0.001) * 45.0),
        )
        if not signal_strength_allows(strength):
            log_entry_skip(self.name, symbol, f"strength={strength:.1f}<elite={effective_elite_min_percent():.0f}")
            return
        if not await portfolio_total_capacity(self._db):
            log_entry_skip(self.name, symbol, "max_elite_positions")
            return
        if not await engine_has_capacity(self._db, self.name, "SMC_MAX_CONCURRENT", 4):
            log_entry_skip(self.name, symbol, "engine_capacity")
            return

        qty = 0.001
        ok_heat, heat_reason = await portfolio_heat_allows(self._db, self._client, qty * entry)
        if not ok_heat:
            log_entry_skip(self.name, symbol, heat_reason)
            return

        fill = await self._client.place_market_guarded(
            symbol,
            "BUY",
            qty,
            entry,
            spread_bps_override=spread_bps,
            stream=self._stream,
        )
        if not fill:
            log_entry_skip(self.name, symbol, "order_blocked_spread_or_notional")
            return

        stop_pct = 0.015
        stop_price = entry * (1 - stop_pct)
        stop_id = None

        if stop_market_enabled():
            stop_resp = await self._client.place_stop_market(
                symbol,
                "SELL",
                stop_price,
                qty,
                reference_price=entry,
                spread_bps_override=spread_bps,
                stream=self._stream,
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
            side="BUY",
            quantity=qty,
            entry_price=entry,
            stop_order_id=stop_id,
            updated_at=now,
            paper=self._client.paper_trading,
        )
        logger.info("SMC macro %s bias=%s strength=%.1f entry=%s stop=%s", symbol, bias, strength, entry, stop_price)
