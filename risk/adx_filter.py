"""فلتر ADX — طبقة مضافة (افتراضي: معطّل)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import get_settings
from core.technical.indicators import adx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdxFilterResult:
    allowed: bool
    reason: str
    adx_value: float | None = None


def check_adx_filter(symbol: str) -> AdxFilterResult:
    """يرفض الدخول التلقائي إذا السوق عرضي (ADX < عتبة)."""
    try:
        settings = get_settings()
        if not bool(getattr(settings, "adx_filter_enabled", False)):
            return AdxFilterResult(True, "ADX Filter معطّل — تمرير")

        period = int(getattr(settings, "adx_period", 14) or 14)
        min_trend = float(getattr(settings, "adx_min_trend", 20.0) or 20.0)
        timeframe = str(getattr(settings, "adx_timeframe", None) or "15m")

        from data.ohlcv_fetcher import OHLCVFetcher

        candles = OHLCVFetcher().fetch(symbol, timeframe, limit=max(80, period * 3))
        value = adx(candles or [], period=period)
        if value is None:
            # بيانات ناقصة: لا نكسر التداول — تمرير آمن
            return AdxFilterResult(True, "ADX غير متوفر — تمرير آمن", None)
        if value < min_trend:
            return AdxFilterResult(
                False,
                f"ADX Filter: سوق عرضي ADX={value:.1f} < {min_trend:.1f}",
                value,
            )
        return AdxFilterResult(True, f"ADX OK ({value:.1f})", value)
    except Exception as exc:  # noqa: BLE001
        logger.warning("check_adx_filter(%s) فشل: %s", symbol, exc)
        return AdxFilterResult(True, f"ADX خطأ — تمرير آمن: {exc}")
