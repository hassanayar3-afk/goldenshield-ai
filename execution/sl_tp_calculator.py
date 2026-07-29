"""حساب Stop Loss و Take Profit."""

from __future__ import annotations

from config.settings import get_settings


def calculate_sl_tp(
    entry_price: float,
    *,
    sl_pct: float | None = None,
    rr_ratio: float | None = None,
    side: str = "buy",
) -> tuple[float, float]:
    if entry_price <= 0:
        return 0.0, 0.0

    settings = get_settings()
    sl = sl_pct if sl_pct is not None else settings.default_sl_pct
    rr = rr_ratio if rr_ratio is not None else settings.default_rr_ratio

    if side == "buy":
        stop_loss = entry_price * (1 - sl)
        risk = entry_price - stop_loss
        take_profit = entry_price + (risk * rr)
    else:
        stop_loss = entry_price * (1 + sl)
        risk = stop_loss - entry_price
        take_profit = entry_price - (risk * rr)

    return round(stop_loss, 8), round(take_profit, 8)
