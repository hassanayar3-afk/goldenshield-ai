"""تخارج ذكي — استراتيجية الربح الجزئي (Partial Take Profit).

الطبقات (قابلة للضبط عبر YAML/ENV، افتراضي حسب طلب المشروع):
  TP1: إغلاق 50% عند 1R + نقل SL إلى التعادل (Risk-Free)
  TP2: إغلاق 30% من الأصل عند 2R + تفعيل Trailing
  TP3: إغلاق المتبقي (~20%) عند 3R — أو ملاحقة بالـ Trail إن عُطّل الإغلاق الكامل

طبقة مضافة فوق Breakeven — لا تكسر المسار عند الفشل.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from config.settings import get_settings
from execution.models.order import OrderSide
from execution.models.trade import Position

logger = logging.getLogger(__name__)


def _cfg() -> dict:
    raw = getattr(get_settings(), "institutional_v13", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _flag(key: str, default: bool = False) -> bool:
    env_key = key.upper()
    if os.getenv(env_key) is not None:
        return os.getenv(env_key, "").strip().lower() in {"1", "true", "yes", "on"}
    # أسماء ENV صريحة للاستراتيجية
    aliases = {
        "multi_tier_tp_enabled": "PARTIAL_TP_ENABLED",
        "structural_trailing_enabled": "PARTIAL_TP_TRAIL_ENABLED",
        "partial_tp3_close_enabled": "PARTIAL_TP3_CLOSE_ENABLED",
    }
    alias = aliases.get(key)
    if alias and os.getenv(alias) is not None:
        return os.getenv(alias, "").strip().lower() in {"1", "true", "yes", "on"}
    cfg = _cfg()
    if key in cfg:
        return bool(cfg[key])
    return default


def _num(key: str, default: float) -> float:
    aliases = {
        "multi_tier_tp1_pct": "PARTIAL_TP1_PCT",
        "multi_tier_tp2_pct": "PARTIAL_TP2_PCT",
        "multi_tier_runner_pct": "PARTIAL_TP3_PCT",
        "multi_tier_tp1_r": "PARTIAL_TP1_R",
        "multi_tier_tp2_r": "PARTIAL_TP2_R",
        "multi_tier_tp3_r": "PARTIAL_TP3_R",
    }
    env_name = aliases.get(key, key.upper())
    raw = os.getenv(env_name)
    if raw is not None and str(raw).strip() != "":
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
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


def _estimate_original_amount(position: Position, closed_pct_so_far: float) -> float:
    """تقدير الحجم الأصلي من المتبقي + نسب الطبقات السابقة."""
    rem = max(1.0 - float(closed_pct_so_far), 0.01)
    initial = float(getattr(position, "initial_amount", 0) or 0)
    if initial > 0:
        return initial
    return float(position.amount) / rem


def _close_amount_for_tranche(
    position: Position,
    *,
    tranche_pct_of_original: float,
    closed_pct_so_far: float,
) -> float:
    original = _estimate_original_amount(position, closed_pct_so_far)
    want = original * float(tranche_pct_of_original)
    # لا تتجاوز المتبقي؛ اترك غباراً صغيراً إن لزم
    capped = min(float(position.amount), max(want, 0.0))
    return round(capped, 8)


def evaluate_multi_tier_tp(position: Position, current_price: float) -> SmartExitAction:
    """Partial TP: 50% @1R+BE → 30% @2R+Trail → 20% @3R (أو runner بالـ Trail)."""
    try:
        if not _flag("multi_tier_tp_enabled", True):
            return SmartExitAction()

        settings = get_settings()
        if not settings.breakeven_enabled:
            return SmartExitAction()

        r = _r_multiple(position, current_price)
        tier = int(getattr(position, "exit_tier", 0) or 0)

        # افتراضي المشروع: 50% / 30% / 20%
        tp1 = _num("multi_tier_tp1_pct", 0.50)
        tp2 = _num("multi_tier_tp2_pct", 0.30)
        tp3 = _num("multi_tier_runner_pct", 0.20)
        r1 = _num("multi_tier_tp1_r", 1.0)
        r2 = _num("multi_tier_tp2_r", 2.0)
        r3 = _num("multi_tier_tp3_r", 3.0)
        close_tp3 = _flag("partial_tp3_close_enabled", True)

        # تطبيع النسب إن لم تُجمّع إلى 1
        total = tp1 + tp2 + tp3
        if total > 0 and abs(total - 1.0) > 0.05:
            tp1, tp2, tp3 = tp1 / total, tp2 / total, tp3 / total

        # —— TP1 ——
        if tier < 1 and r >= r1:
            amount = _close_amount_for_tranche(
                position, tranche_pct_of_original=tp1, closed_pct_so_far=0.0
            )
            if amount <= 0:
                return SmartExitAction()
            return SmartExitAction(
                partial_exit_amount=amount,
                new_stop_loss=float(position.entry_price),
                mark_breakeven=True,
                next_exit_tier=1,
                reason=(
                    f"Partial TP1: إغلاق {tp1*100:.0f}% @ {r1:.1f}R "
                    f"+ نقل SL إلى التعادل (صفقة بلا مخاطرة)"
                ),
            )

        # —— TP2 ——
        if tier < 2 and r >= r2:
            amount = _close_amount_for_tranche(
                position, tranche_pct_of_original=tp2, closed_pct_so_far=tp1
            )
            if amount <= 0:
                return SmartExitAction(
                    next_exit_tier=2,
                    enable_structural_trail=True,
                    reason="Partial TP2: تفعيل Trailing (لا كمية متبقية كافية)",
                )
            return SmartExitAction(
                partial_exit_amount=amount,
                next_exit_tier=2,
                enable_structural_trail=True,
                reason=(
                    f"Partial TP2: إغلاق {tp2*100:.0f}% @ {r2:.1f}R "
                    f"+ Trailing للمتبقي (~{tp3*100:.0f}%)"
                ),
            )

        # —— TP3: إغلاق المتبقي أو ملاحقته ——
        if tier < 3 and r >= r3:
            if close_tp3 and position.amount > 0:
                return SmartExitAction(
                    partial_exit_amount=round(float(position.amount), 8),
                    next_exit_tier=3,
                    enable_structural_trail=True,
                    reason=(
                        f"Partial TP3: إغلاق المتبقي (~{tp3*100:.0f}%) @ {r3:.1f}R"
                    ),
                )
            return SmartExitAction(
                next_exit_tier=3,
                enable_structural_trail=True,
                reason=f"Partial TP3: ملاحقة بالـ Trailing @ {r3:.1f}R (بدون إغلاق كامل)",
            )

        return SmartExitAction()
    except Exception as exc:  # noqa: BLE001
        logger.warning("evaluate_multi_tier_tp فشل: %s", exc)
        return SmartExitAction()


def structural_trail_sl(
    position: Position,
    current_price: float,
    *,
    swing_level: float | None = None,
) -> float | None:
    """تحريك SL خلف قاع/قمة هيكل إن وُجدت، وإلا خلف مسافة R-factor.

    يُفعَّل بعد TP1 (تعادل) أو صراحة بعد TP2.
    """
    try:
        if not _flag("structural_trailing_enabled", True):
            return None
        if not get_settings().trailing_stop_enabled:
            return None
        tier = int(getattr(position, "exit_tier", 0) or 0)
        if tier < 1 and not position.breakeven_applied:
            return None

        settings = get_settings()
        risk = position.risk_per_unit
        if risk <= 0:
            # بعد نقل SL للتعادل يصبح risk_per_unit=0 — نستخدم 1% من الدخول كمرجع للـ trail
            risk = abs(float(position.entry_price)) * 0.01
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

        # بعد TP2: trail أضيق قليلاً لحماية أرباح الجزء الأخير
        factor = float(settings.trailing_stop_factor)
        if tier >= 2:
            factor = max(0.25, factor * 0.75)

        if position.side == OrderSide.BUY:
            candidate = current_price - risk * factor
            # لا تنزل تحت التعادل بعد TP1
            if position.breakeven_applied:
                candidate = max(candidate, float(position.entry_price))
            if candidate > position.stop_loss:
                return candidate
        else:
            candidate = current_price + risk * factor
            if position.breakeven_applied:
                candidate = min(candidate, float(position.entry_price))
            if position.stop_loss == 0 or candidate < position.stop_loss:
                return candidate
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("structural_trail_sl فشل: %s", exc)
        return None
