"""
UI control plane — pause engines, close positions (paper + live guarded market exits).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from database.db_manager import PositionRow
from utils.control_state import engines_paused, set_engines_paused
from utils.logger_config import setup_logger

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager
    from gateway.stream_service import StreamService
    from gateway.sync_service import SyncService

logger = setup_logger("saqr.control")

PAUSE_KEY = "engines_paused"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlService:
    def __init__(
        self,
        db: "DatabaseManager",
        client: "BinanceClient",
        stream: "StreamService",
        hub: "ConnectionManager",
        sync: Optional["SyncService"] = None,
    ) -> None:
        self._db = db
        self._client = client
        self._stream = stream
        self._hub = hub
        self._sync = sync

    async def load_runtime_flags(self) -> None:
        raw = await self._db.get_runtime_state_async(PAUSE_KEY)
        set_engines_paused(raw == "true")

    async def set_paused(self, paused: bool) -> Dict[str, Any]:
        set_engines_paused(paused)
        await self._db.set_runtime_state_async(PAUSE_KEY, "true" if paused else "false", _utc_now())
        payload = {"type": "control", "action": "pause" if paused else "resume", "paused": paused}
        await self._hub.publish(payload)
        logger.info("Engines paused=%s", paused)
        return payload

    async def toggle_paused(self) -> Dict[str, Any]:
        return await self.set_paused(not engines_paused())

    @staticmethod
    def _mark_price(pos: PositionRow, stream: "StreamService") -> float:
        last = stream.get_last_close(pos.symbol, "1m")
        if last is not None and last > 0:
            return last
        return pos.entry_price

    @staticmethod
    def _unrealized_pnl(pos: PositionRow, mark: float) -> float:
        if pos.side.upper() == "BUY":
            return (mark - pos.entry_price) * pos.quantity
        return (pos.entry_price - mark) * pos.quantity

    async def _close_one(self, pos: PositionRow) -> Dict[str, Any]:
        mark = self._mark_price(pos, self._stream)
        pnl = self._unrealized_pnl(pos, mark)
        exit_side = "SELL" if pos.side.upper() == "BUY" else "BUY"
        spread_bps = self._stream.get_spread_bps(pos.symbol)
        order = await self._client.place_market_guarded(
            pos.symbol,
            exit_side,
            pos.quantity,
            mark,
            spread_bps_override=spread_bps,
        )
        now = _utc_now()
        await self._db.run_dao(
            self._db.record_closed_trade,
            symbol=pos.symbol,
            side=pos.side,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            exit_price=mark,
            pnl=pnl,
            engine=pos.engine,
            closed_at=now,
        )
        await self._db.delete_position_async(pos.symbol)
        return {
            "symbol": pos.symbol,
            "pnl": round(pnl, 6),
            "exit_side": exit_side,
            "filled": order is not None,
        }

    async def _close_matching(self, predicate) -> Dict[str, Any]:
        positions = await self._db.list_positions_async()
        closed: List[Dict[str, Any]] = []
        for pos in positions:
            mark = self._mark_price(pos, self._stream)
            pnl = self._unrealized_pnl(pos, mark)
            if predicate(pnl):
                closed.append(await self._close_one(pos))
        if self._sync:
            await self._sync.sync_once()
        stats = await self.trade_stats()
        result = {
            "type": "control",
            "closed_count": len(closed),
            "closed": closed,
            **stats,
        }
        await self._hub.publish(result)
        return result

    async def close_all(self) -> Dict[str, Any]:
        return await self._close_matching(lambda _pnl: True)

    async def close_winners(self) -> Dict[str, Any]:
        return await self._close_matching(lambda pnl: pnl > 0)

    async def close_losers(self) -> Dict[str, Any]:
        return await self._close_matching(lambda pnl: pnl < 0)

    async def trade_stats(self) -> Dict[str, Any]:
        wins, losses = await self._db.closed_trade_counts_async()
        return {
            "wins": wins,
            "losses": losses,
            "engines_paused": engines_paused(),
        }

    async def handle_ui_action(self, action: str) -> Dict[str, Any]:
        action = (action or "").strip().lower()
        try:
            if action == "pause":
                return await self.set_paused(True)
            if action == "resume":
                return await self.set_paused(False)
            if action == "toggle":
                return await self.toggle_paused()
            if action == "close_all":
                out = await self.close_all()
                out["action"] = action
                return out
            if action == "close_winners":
                out = await self.close_winners()
                out["action"] = action
                return out
            if action == "close_losers":
                out = await self.close_losers()
                out["action"] = action
                return out
        except Exception as exc:
            logger.error("Control action %s failed: %s", action, exc)
            err = {"type": "control", "action": action, "ok": False, "error": str(exc)}
            await self._hub.publish(err)
            return err
        return {"type": "control", "action": action, "ok": False, "error": "unknown_action"}

    async def handle_ws_message(self, raw: str) -> None:
        raw = raw.strip()
        if raw.lower() == "ping":
            await self._hub.publish({"type": "pong"})
            return
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(msg, dict):
            return
        if msg.get("type") != "ui":
            return
        await self.handle_ui_action(str(msg.get("action", "")))
