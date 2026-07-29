"""الدخول المتدرج 50/50 — طبقة مضافة (افتراضي: معطّل)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PartialScalingPlan:
    enabled: bool
    initial_amount: float
    add_amount: float
    reason: str


def plan_partial_scaling(full_amount: float) -> PartialScalingPlan:
    try:
        settings = get_settings()
        if not bool(getattr(settings, "partial_scaling_enabled", False)):
            return PartialScalingPlan(False, full_amount, 0.0, "Partial Scaling معطّل")
        if full_amount <= 0:
            return PartialScalingPlan(False, 0.0, 0.0, "حجم صفر")

        initial_pct = float(getattr(settings, "partial_scaling_initial_pct", 50.0) or 50.0) / 100.0
        add_pct = float(getattr(settings, "partial_scaling_add_pct", 50.0) or 50.0) / 100.0
        initial_pct = min(max(initial_pct, 0.05), 0.95)
        add_pct = min(max(add_pct, 0.05), 1.0 - initial_pct)

        initial = round(full_amount * initial_pct, 8)
        add = round(full_amount * add_pct, 8)
        if initial <= 0:
            return PartialScalingPlan(False, full_amount, 0.0, "حجم أولي غير صالح")
        return PartialScalingPlan(
            True,
            initial,
            add,
            f"Partial Scaling: دخول {initial_pct:.0%} + إضافة لاحقة {add_pct:.0%}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("plan_partial_scaling فشل: %s", exc)
        return PartialScalingPlan(False, full_amount, 0.0, f"خطأ — حجم كامل: {exc}")


def should_add_scaling(
    *,
    side: str,
    entry_price: float,
    current_price: float,
    stop_loss: float,
) -> tuple[bool, str]:
    """يضيف الجزء الثاني فقط إذا تحرك السعر في اتجاه الربح بمقدار جزء من مخاطرة الصفقة."""
    try:
        settings = get_settings()
        trigger_r = float(getattr(settings, "partial_scaling_trigger_r", 0.5) or 0.5)
        risk = abs(entry_price - stop_loss)
        if risk <= 0 or entry_price <= 0 or current_price <= 0:
            return False, "بيانات ناقصة للإضافة"
        side_l = (side or "buy").lower()
        if side_l in {"sell", "short"}:
            move = entry_price - current_price
        else:
            move = current_price - entry_price
        if move >= risk * trigger_r:
            return True, f"Partial Scaling: تحرك +{move / risk:.2f}R ≥ {trigger_r:.2f}R"
        return False, "لم يتحقق شرط إضافة الحجم بعد"
    except Exception as exc:  # noqa: BLE001
        logger.warning("should_add_scaling فشل: %s", exc)
        return False, f"خطأ شرط الإضافة: {exc}"
