"""إغلاق فوري لجميع المراكز — Emergency Flat."""

from __future__ import annotations

from dataclasses import dataclass

from execution.models.order import OrderSide
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager


@dataclass(frozen=True)
class EmergencyCloseResult:
    symbol: str
    pnl: float
    position_id: str


def _position_pnl(position, exit_price: float) -> float:
    if position.side == OrderSide.BUY:
        return (exit_price - position.entry_price) * position.amount
    return (position.entry_price - exit_price) * position.amount


def emergency_flat(
    order_manager: OrderManager,
    position_manager: PositionManager,
    *,
    prices: dict[str, float] | None = None,
) -> list[EmergencyCloseResult]:
    results: list[EmergencyCloseResult] = []
    price_map = prices or {}

    for position in list(position_manager.all()):
        reference = price_map.get(position.symbol, position.entry_price)
        pnl = _position_pnl(position, reference)
        close_side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
        order_manager.create_market_order(
            position.symbol,
            close_side,
            position.amount,
            reference_price=reference,
            allow_without_stops=True,
        )
        position_manager.remove(position.symbol)
        results.append(
            EmergencyCloseResult(
                symbol=position.symbol,
                pnl=pnl,
                position_id=position.id,
            )
        )

    return results
