"""سقف الأرباح اليومي — طبقة مضافة (افتراضي: معطّل)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfitCapResult:
    allowed: bool
    reason: str


def check_profit_cap(daily_pnl_pct: float) -> ProfitCapResult:
    try:
        settings = get_settings()
        if not bool(getattr(settings, "profit_cap_enabled", False)):
            return ProfitCapResult(True, "Profit Cap معطّل — تمرير")
        cap = float(getattr(settings, "profit_cap_daily_pct", 3.0) or 3.0)
        if daily_pnl_pct >= cap:
            return ProfitCapResult(
                False,
                f"Profit Cap: ربح يومي {daily_pnl_pct:+.2f}% ≥ سقف {cap:.2f}% — توقف دخول",
            )
        return ProfitCapResult(True, f"ضمن سقف الربح ({daily_pnl_pct:+.2f}% / {cap:.2f}%)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("check_profit_cap فشل: %s", exc)
        return ProfitCapResult(True, f"Profit Cap خطأ — تمرير آمن: {exc}")
