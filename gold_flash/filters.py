"""فلاتر gold_flash — سبريد، عمق دفتر، تأكيد شمعة."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class FlashFilterResult:
    allowed: bool
    reason: str


def smart_slippage_breaker(
    *,
    spread_pct: float,
    bid_depth_usdt: float,
    ask_depth_usdt: float,
    min_depth_usdt: float = 5000.0,
    max_spread_pct: float | None = None,
) -> FlashFilterResult:
    settings = get_settings()
    cap = max_spread_pct if max_spread_pct is not None else float(
        getattr(settings, "max_slippage_pct", 0.15) or 0.15
    )
    if spread_pct > cap:
        return FlashFilterResult(False, f"Spread {spread_pct:.3f}% > {cap:.3f}%")
    depth = min(bid_depth_usdt, ask_depth_usdt)
    if depth < min_depth_usdt:
        return FlashFilterResult(False, f"Order book depth {depth:.0f} USDT ضعيف")
    return FlashFilterResult(True, "Slippage breaker OK")


def candle_confirmation_guard(
    *,
    prev_close: float,
    last_close: float,
    side: str,
) -> FlashFilterResult:
    if prev_close <= 0 or last_close <= 0:
        return FlashFilterResult(False, "شموع غير صالحة")
    if side == "buy" and last_close < prev_close:
        return FlashFilterResult(False, "Candle Guard: لا تأكيد شراء")
    if side == "sell" and last_close > prev_close:
        return FlashFilterResult(False, "Candle Guard: لا تأكيد بيع")
    return FlashFilterResult(True, "Candle confirmed")
