"""تفضيلات الصفقة — لوت، SL، TP لكل زوج."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class TradePrefs:
    risk_pct: float
    sl_pct: float
    rr_ratio: float

    @classmethod
    def defaults(cls) -> TradePrefs:
        settings = get_settings()
        return cls(
            risk_pct=settings.risk_per_trade_pct,
            sl_pct=settings.default_sl_pct,
            rr_ratio=settings.default_rr_ratio,
        )

    def label(self) -> str:
        return f"مخاطرة {self.risk_pct:.1f}% | SL {self.sl_pct * 100:.0f}% | R:R 1:{self.rr_ratio:.0f}"
