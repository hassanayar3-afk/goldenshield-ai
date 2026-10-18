"""
Boot recovery — reconcile SQLite positions with Binance and re-bind STOP_MARKET protection.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from data_highway.sqlite_store import PositionRow
from data_highway.logging_config import setup_logger
from data_highway.runtime_env import recovery_stop_fraction, stop_market_enabled

if TYPE_CHECKING:
    from data_highway.sqlite_store import DatabaseManager
    from gateway_api.binance_client import BinanceClient
    from gateway_api.connection_manager import ConnectionManager
    from gateway_api.stream_service import StreamService

logger = setup_logger("saqr.recovery")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RecoveryService:
    def __init__(
        self,
        db: "DatabaseManager",
        client: "BinanceClient",
        hub: "ConnectionManager",
        stream: Optional["StreamService"] = None,
    ) -> None:
        self._db = db
        self._client = client
        self._hub = hub
        self._stream = stream
        self._last_report: Dict[str, Any] = {}

    @property
    def last_report(self) -> Dict[str, Any]:
        return dict(self._last_report)

    async def run_boot_recovery(self) -> Dict[str, Any]:
        """
        1) Load open positions from SQLite (survived power loss).
        2) Compare with exchange open orders (live) or protection_orders (paper).
        3) Re-create missing STOP_MARKET orders on Binance servers.
        """
        positions = await self._db.list_positions_async()
        exchange_stops = await self._collect_exchange_stops()
        actions: List[Dict[str, Any]] = []
        rebound = 0
        verified = 0

        for pos in positions:
            has_stop = self._position_has_stop(pos, exchange_stops)
            if has_stop:
                verified += 1
                actions.append({"symbol": pos.symbol, "action": "verified_stop"})
                continue

            rebound_result = await self._rebind_stop_market(pos)
            if rebound_result:
                rebound += 1
                actions.append(rebound_result)
            else:
                actions.append({"symbol": pos.symbol, "action": "rebind_failed"})

        report = {
            "type": "recovery",
            "positions": len(positions),
            "verified_stops": verified,
            "rebound_stops": rebound,
            "actions": actions,
            "recovered_at": _utc_now(),
            "paper": self._client.paper_trading,
        }
        self._last_report = report
        await self._hub.publish(report)
        logger.info(
            "Boot recovery complete: positions=%s verified=%s rebound=%s",
            len(positions),
            verified,
            rebound,
        )
        return report

    async def _collect_exchange_stops(self) -> Set[str]:
        ids: Set[str] = set()
        if self._client.paper_trading:
            for row in await self._db.list_protection_orders_async():
                if str(row.get("status", "")).upper() in ("NEW", "PARTIALLY_FILLED"):
                    ids.add(str(row["client_order_id"]))
            return ids

        try:
            orders = await self._client.open_orders()
        except Exception as exc:
            logger.error("open_orders during recovery failed: %s", exc)
            orders = []

        for order in orders:
            if str(order.get("type", "")).upper() != "STOP_MARKET":
                continue
            cid = str(order.get("clientOrderId") or order.get("orderId") or "")
            if cid:
                ids.add(cid)
        return ids

    def _position_has_stop(self, pos: PositionRow, stop_ids: Set[str]) -> bool:
        if pos.stop_order_id and pos.stop_order_id in stop_ids:
            return True
        if pos.stop_order_id and self._client.paper_trading:
            return pos.stop_order_id in stop_ids
        return False

    async def _rebind_stop_market(self, pos: PositionRow) -> Optional[Dict[str, Any]]:
        if not stop_market_enabled():
            return None

        entry = pos.entry_price
        if self._stream is not None:
            live = self._stream.get_last_close(pos.symbol, "1m")
            if live:
                entry = live

        stop_pct = recovery_stop_fraction()
        if pos.side.upper() == "BUY":
            stop_price = entry * (1 - stop_pct)
            stop_side = "SELL"
        else:
            stop_price = entry * (1 + stop_pct)
            stop_side = "BUY"

        spread_bps = self._stream.get_spread_bps(pos.symbol) if self._stream else None
        resp = await self._client.place_stop_market(
            pos.symbol,
            stop_side,
            stop_price,
            pos.quantity,
            reference_price=entry,
            spread_bps_override=spread_bps,
        )
        if not resp:
            return None

        stop_id = str(resp.get("clientOrderId") or resp.get("orderId") or "")
        now = _utc_now()
        await self._db.register_protection_order_async(
            stop_id,
            pos.symbol,
            stop_price,
            str(resp.get("status", "NEW")),
            now,
        )
        await self._db.upsert_position_async(
            PositionRow(
                symbol=pos.symbol,
                side=pos.side,
                quantity=pos.quantity,
                entry_price=pos.entry_price,
                stop_order_id=stop_id,
                engine=pos.engine,
                updated_at=now,
            )
        )
        logger.warning("Re-bound STOP_MARKET for %s at %s", pos.symbol, stop_price)
        return {
            "symbol": pos.symbol,
            "action": "rebound_stop_market",
            "stop_order_id": stop_id,
            "stop_price": stop_price,
        }
