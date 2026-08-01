"""تخارج ذكي: Multi-Tier TP + Structural Trailing (طبقات فوق Breakeven)."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from execution.models.order import OrderSide
from execution.models.trade import Position


def _cfg() -> dict:
    raw = getattr(get_settings(), "institutional_v13", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _flag(key: str, default: bool = False) -> bool:
    cfg = _cfg()
    if key in cfg:
        return bool(cfg[key])
    return default


def _num(key: str, default: float) -> float:
    cfg = _cfg()
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SmartExitAction:
    partial_exit_amount: float = 0.0
    new_stop_loss: float | None = None
    mark_breakeven: bool = False
    next_exit_tier: int | None = None
    enable_structural_trail: bool = False
    reason: str = ""


def _r_multiple(position: Position, price: float) -> float:
    risk = position.risk_per_unit
    if risk <= 0:
        return 0.0
    if position.side == OrderSide.BUY:
        return (price - position.entry_price) / risk
    return (position.entry_price - price) / risk


def evaluate_multi_tier_tp(position: Position, current_price: float) -> SmartExitAction:
    """30% @1:1 + BE → 40% @1:2 + trail → 30% runner."""
    if not _flag("multi_tier_tp_enabled", True):
        return SmartExitAction()

    settings = get_settings()
    if not settings.breakeven_enabled:
        return SmartExitAction()

    r = _r_multiple(position, current_price)
    tier = int(getattr(position, "exit_tier", 0) or 0)
    tp1 = _num("multi_tier_tp1_pct", 0.30)
    tp2 = _num("multi_tier_tp2_pct", 0.40)

    # تقدير الحجم الأصلي: إن أُغلق جزء سابقاً نستخدم المبلغ الحالي + تقريبي
    # نستخدم المبلغ الحالي كنسبة من المتبقي عند كل طبقة
    if tier < 1 and r >= 1.0:
        amount = round(position.amount * tp1, 8)
        return SmartExitAction(
            partial_exit_amount=amount,
            new_stop_loss=position.entry_price,
            mark_breakeven=True,
            next_exit_tier=1,
            reason="Multi-Tier TP1 30% @1:1 + Breakeven",
        )

    if tier < 2 and r >= 2.0:
        # 40% من الحجم الأصلي ≈ نسبة من المتبقي بعد إغلاق 30%: 0.4/0.7
        remaining_frac = max(1.0 - tp1, 0.01)
        frac_of_remaining = min(1.0, tp2 / remaining_frac)
        amount = round(position.amount * frac_of_remaining, 8)
        return SmartExitAction(
            partial_exit_amount=amount,
            next_exit_tier=2,
            enable_structural_trail=True,
            reason="Multi-Tier TP2 40% @1:2 + تفعيل Trailing",
        )

    return SmartExitAction()


def structural_trail_sl(
    position: Position,
    current_price: float,
    *,
    swing_level: float | None = None,
) -> float | None:
    """تحريك SL خلف قاع/قمة هيكل إن وُجدت، وإلا خلف مسافة R-factor."""
    if not _flag("structural_trailing_enabled", True):
        return None
    if not get_settings().trailing_stop_enabled:
        return None
    if int(getattr(position, "exit_tier", 0) or 0) < 2 and not position.breakeven_applied:
        return None

    settings = get_settings()
    risk = position.risk_per_unit
    if risk <= 0:
        return None

    if swing_level is not None and swing_level > 0:
        if position.side == OrderSide.BUY:
            candidate = min(swing_level, current_price)
            if candidate > position.stop_loss and candidate < current_price:
                return candidate
        else:
            candidate = max(swing_level, current_price)
            if (candidate < position.stop_loss or position.stop_loss == 0) and candidate > current_price:
                return candidate

    # احتياطي: trail بمقدار factor من المخاطرة
    factor = float(settings.trailing_stop_factor)
    if position.side == OrderSide.BUY:
        candidate = current_price - risk * factor
        if candidate > position.stop_loss:
            return candidate
    else:
        candidate = current_price + risk * factor
        if position.stop_loss == 0 or candidate < position.stop_loss:
            return candidate
    return None
