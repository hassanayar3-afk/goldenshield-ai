"""نمو تراكمي + تعديل المخاطرة حسب سلسلة الأرباح/الخسائر."""

from __future__ import annotations

from config.settings import get_settings


def risk_amount(balance: float, risk_pct: float | None = None) -> float:
    settings = get_settings()
    pct = risk_pct if risk_pct is not None else settings.risk_per_trade_pct
    return balance * (pct / 100)


def effective_risk_pct(
    risk_pct: float | None = None,
    *,
    consecutive_wins: int = 0,
    consecutive_losses: int = 0,
) -> float:
    settings = get_settings()
    base = risk_pct if risk_pct is not None else settings.risk_per_trade_pct
    try:
        from risk.advanced_shields import streak_adjusted_risk_pct

        return streak_adjusted_risk_pct(
            base,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
        ).risk_pct
    except Exception:
        return base
