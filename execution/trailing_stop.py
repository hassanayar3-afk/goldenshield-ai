"""Trailing Stop بعد Breakeven + Partial Exit."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from execution.models.order import OrderSide
from execution.models.trade import Position


@dataclass(frozen=True)
class TrailingAction:
    new_stop_loss: float | None = None
    reason: str = ""


def evaluate_trailing_stop(position: Position, current_price: float) -> TrailingAction:
    """
    بعد إغلاق 50% ونقل SL إلى التعادل:
    حرّك SL مع السعر. إن أصبح risk_per_unit=0 بعد التعادل،
    نشتق مسافة التتبع من مسافة TP الأصلية.
    """
    settings = get_settings()
    if not getattr(settings, "trailing_stop_enabled", True):
        return TrailingAction()
    if not position.partial_exit_done or not position.breakeven_applied:
        return TrailingAction()
    if current_price <= 0:
        return TrailingAction()

    trail_factor = float(getattr(settings, "trailing_stop_factor", 0.5))
    risk = position.risk_per_unit
    if risk <= 0:
        # بعد التعادل: تقدير المخاطرة الأصلية من مسافة TP وR:R
        rr = max(float(getattr(settings, "default_rr_ratio", 3.0)), 1.0)
        risk = abs(position.take_profit - position.entry_price) / rr
    trail = risk * trail_factor
    if trail <= 0:
        return TrailingAction()

    if position.side == OrderSide.BUY:
        if current_price <= position.entry_price:
            return TrailingAction()
        candidate = current_price - trail
        candidate = max(candidate, position.entry_price)
        if candidate > position.stop_loss + (trail * 0.05):
            return TrailingAction(
                new_stop_loss=round(candidate, 8),
                reason=f"Trailing Stop صاعد → SL {candidate:.5f}",
            )
    else:
        if current_price >= position.entry_price:
            return TrailingAction()
        candidate = current_price + trail
        candidate = min(candidate, position.entry_price)
        if candidate < position.stop_loss - (trail * 0.05):
            return TrailingAction(
                new_stop_loss=round(candidate, 8),
                reason=f"Trailing Stop هابط → SL {candidate:.5f}",
            )

    return TrailingAction()
