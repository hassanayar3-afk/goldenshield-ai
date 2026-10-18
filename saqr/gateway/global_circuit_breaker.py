"""
Portfolio-wide circuit breaker — trips on drawdown / heat, closes all, pauses engines.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from utils.control_state import engines_paused
from utils.logger_config import setup_logger
from utils.runtime_env import portfolio_heat_cap_fraction

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager
    from gateway.control_service import ControlService
    from gateway.stream_service import StreamService

logger = setup_logger("saqr.circuit_breaker")

STATE_KEY = "global_circuit_tripped_at"
DAY_BASELINE_KEY = "day_equity_baseline"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loss_trip_fraction(default: float = 0.07) -> float:
    """Env may be fraction (0.07) or percent (7)."""
    try:
        raw = float(
            os.getenv(
                "GLOBAL_CIRCUIT_LOSS_PCT",
                os.getenv("PORTFOLIO_HEAT_CAP_PCT", str(default)),
            )
        )
    except ValueError:
        return default
    if raw >= 1.0:
        return raw / 100.0
    return raw


class GlobalCircuitBreaker:
    def __init__(
        self,
        db: "DatabaseManager",
        client: "BinanceClient",
        stream: "StreamService",
        control: "ControlService",
        hub: "ConnectionManager",
    ) -> None:
        self._db = db
        self._client = client
        self._stream = stream
        self._control = control
        self._hub = hub
        self._tripped = False

    @property
    def tripped(self) -> bool:
        return self._tripped

    async def load_state(self) -> None:
        tripped = await self._db.get_runtime_state_async(STATE_KEY)
        self._tripped = bool(tripped)
        if self._tripped:
            await self._control.set_paused(True)

    async def evaluate(self, sync_snapshot: Dict[str, Any]) -> None:
        try:
            if self._tripped or engines_paused():
                return

            positions = await self._db.list_positions_async()
            total_unrealized = float(sync_snapshot.get("total_unrealized_pnl") or 0.0)
            if not positions and total_unrealized == 0.0:
                return

            balances = sync_snapshot.get("balances") or []
            equity = 0.0
            for b in balances:
                if str(b.get("asset", "")).upper() == "USDT":
                    equity += float(b.get("free", 0)) + float(b.get("locked", 0))
            if equity <= 0:
                equity = 10_000.0

            baseline_raw = await self._db.get_runtime_state_async(DAY_BASELINE_KEY)
            if not baseline_raw:
                await self._db.set_runtime_state_async(DAY_BASELINE_KEY, str(equity), _utc_now())
                baseline = equity
            else:
                baseline = float(baseline_raw)

            day_pnl = equity - baseline
            day_pct = day_pnl / baseline if baseline > 0 else 0.0
            unrealized_pct = total_unrealized / equity if equity > 0 else 0.0
            heat_cap = portfolio_heat_cap_fraction()
            loss_cap = _loss_trip_fraction()

            trip_reason: Optional[str] = None
            if unrealized_pct < 0 and abs(unrealized_pct) >= loss_cap:
                trip_reason = f"unrealized_loss {unrealized_pct:.4f} >= -{loss_cap}"
            elif day_pct < 0 and abs(day_pct) >= loss_cap:
                trip_reason = f"day_loss {day_pct:.4f} >= -{loss_cap}"
            elif positions:
                open_notional = sum(p.quantity * p.entry_price for p in positions)
                heat = (open_notional / equity) if equity > 0 else 0.0
                if heat > heat_cap:
                    trip_reason = f"portfolio_heat {heat:.4f}>{heat_cap}"

            if not trip_reason:
                return

            await self._trip(trip_reason, sync_snapshot)
        except Exception as exc:
            logger.error("Global circuit evaluate failed: %s", exc)

    async def _trip(self, reason: str, sync_snapshot: Dict[str, Any]) -> None:
        self._tripped = True
        logger.error("GLOBAL CIRCUIT BREAKER TRIP: %s", reason)
        await self._db.set_runtime_state_async(STATE_KEY, _utc_now(), _utc_now())
        await self._control.set_paused(True)
        try:
            result = await self._control.close_all(emergency=True)
            logger.error("Circuit close_all: closed=%s", result.get("closed_count"))
        except Exception as exc:
            logger.error("Circuit close_all failed: %s", exc)
        await self._hub.publish(
            {
                "type": "circuit_breaker",
                "tripped": True,
                "reason": reason,
                "sync": sync_snapshot.get("synced_at"),
            }
        )
