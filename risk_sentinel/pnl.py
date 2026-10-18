"""Mark-to-market PnL helpers for open positions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from data_highway.sqlite_store import PositionRow
    from gateway_api.stream_service import StreamService


def mark_price(pos: "PositionRow", stream: Optional["StreamService"]) -> float:
    if stream is not None:
        last = stream.get_last_close(pos.symbol, "1m")
        if last is not None and last > 0:
            return last
    return pos.entry_price


def mark_price_for_symbol(stream: Optional["StreamService"], symbol: str, fallback: float) -> float:
    if stream is None:
        return fallback
    last = stream.get_last_close(symbol, "1m")
    if last is not None and last > 0:
        return last
    return fallback


def unrealized_pnl(pos: "PositionRow", mark: float) -> float:
    if pos.side.upper() == "BUY":
        return (mark - pos.entry_price) * pos.quantity
    return (pos.entry_price - mark) * pos.quantity


def unrealized_pct(pos: "PositionRow", mark: float) -> float:
    if pos.entry_price <= 0:
        return 0.0
    if pos.side.upper() == "BUY":
        return ((mark - pos.entry_price) / pos.entry_price) * 100.0
    return ((pos.entry_price - mark) / pos.entry_price) * 100.0
