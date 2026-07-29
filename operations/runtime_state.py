"""حالة التشغيل المشتركة — إيقاف/استئناف وتفضيلات الصفقة."""

from __future__ import annotations

from dataclasses import dataclass, field

from operations.trade_prefs import TradePrefs


@dataclass
class OperationsRuntime:
    paused: bool = False
    panic_latched: bool = False
    user_stopped: bool = False
    manual_entry_required: bool = True
    _symbol_prefs: dict[str, TradePrefs] = field(default_factory=dict)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        if self.user_stopped:
            return
        self.paused = False
        self.panic_latched = False

    def stop_permanently(self, *, reason: str = "user") -> None:
        from operations.shutdown_guard import request_user_stop

        self.user_stopped = True
        self.paused = True
        self.panic_latched = True
        request_user_stop(reason, source="runtime")

    def get_prefs(self, symbol: str) -> TradePrefs:
        return self._symbol_prefs.get(symbol, TradePrefs.defaults())

    def update_prefs(self, symbol: str, **kwargs) -> TradePrefs:
        current = self.get_prefs(symbol)
        updated = TradePrefs(
            risk_pct=float(kwargs.get("risk_pct", current.risk_pct)),
            sl_pct=float(kwargs.get("sl_pct", current.sl_pct)),
            rr_ratio=float(kwargs.get("rr_ratio", current.rr_ratio)),
        )
        self._symbol_prefs[symbol] = updated
        return updated
