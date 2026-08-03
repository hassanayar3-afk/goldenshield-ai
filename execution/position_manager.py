"""إدارة المراكز المفتوحة."""

from __future__ import annotations

from execution.models.order import OrderSide
from execution.models.trade import Position


class PositionManager:
    def __init__(self) -> None:
        self._positions: dict[str, Position] = {}

    def add(self, position: Position) -> None:
        self._positions[position.symbol] = position

    def get(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)

    def has(self, symbol: str) -> bool:
        return symbol in self._positions

    def remove(self, symbol: str) -> Position | None:
        return self._positions.pop(symbol, None)

    def all(self) -> list[Position]:
        return list(self._positions.values())

    def open_symbols(self) -> set[str]:
        return set(self._positions.keys())

    def count(self) -> int:
        return len(self._positions)

    def reduce_amount(self, symbol: str, amount: float) -> Position | None:
        position = self._positions.get(symbol)
        if position is None:
            return None
        position.amount = round(max(position.amount - amount, 0.0), 8)
        if position.amount <= 0:
            self.remove(symbol)
            return None
        return position

    def update_stop_loss(self, symbol: str, stop_loss: float) -> Position | None:
        position = self._positions.get(symbol)
        if position is None:
            return None
        position.stop_loss = stop_loss
        position.breakeven_applied = True
        return position

    def update_take_profit(self, symbol: str, take_profit: float) -> Position | None:
        position = self._positions.get(symbol)
        if position is None:
            return None
        position.take_profit = take_profit
        return position

    def clear(self) -> None:
        self._positions.clear()
