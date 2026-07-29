"""زر الطوارئ — إغلاق فوري لكل المراكز."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from operations.alert_dispatcher import AlertDispatcher

if TYPE_CHECKING:
    from execution.trade_executor import TradeExecutor


@dataclass(frozen=True)
class PanicResult:
    triggered: bool
    closed_symbols: tuple[str, ...]
    message: str


class PanicButton:
    def __init__(
        self,
        executor: TradeExecutor,
        alert_dispatcher: AlertDispatcher,
    ) -> None:
        self._executor = executor
        self._alerts = alert_dispatcher

    def trigger(
        self,
        prices: dict[str, float],
        *,
        reason: str = "Panic Button",
    ) -> PanicResult:
        closed = self._executor.emergency_close_all(prices)
        symbols = tuple(closed)

        if not symbols:
            return PanicResult(False, (), "لا توجد مراكز مفتوحة للإغلاق.")

        message = f"🚨 {reason}\nتم إغلاق: {', '.join(symbols)}"
        self._alerts.emergency("Panic Button", message)
        return PanicResult(True, symbols, message)
