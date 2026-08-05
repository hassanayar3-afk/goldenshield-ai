# -*- coding: utf-8 -*-
"""فحص دخول مجهري على 5m/1m — انزلاق واتساق الاتجاه (طبقة مضافة)."""

from __future__ import annotations

from dataclasses import dataclass

from core.technical.timeframe_aligner import TrendDirection
from data.models.candle import Candle


@dataclass(frozen=True)
class MicroEntryResult:
    ok: bool
    reason: str


def evaluate_micro_entry(
    *,
    candles_5m: list[Candle] | None,
    candles_1m: list[Candle] | None,
    direction: TrendDirection,
) -> MicroEntryResult:
    """يرفض الدخول عند انزلاق 1m عنيف أو تناقض 5m مع الاتجاه الهرمي."""
    try:
        c5 = list(candles_5m or [])
        c1 = list(candles_1m or [])
        if not c5 and not c1:
            return MicroEntryResult(True, "أطر مجهرية غير متاحة — تخطي آمن")

        notes: list[str] = []

        if c5 and len(c5) >= 3 and direction in {TrendDirection.BULLISH, TrendDirection.BEARISH}:
            last = c5[-1]
            prev = c5[-2]
            bull_bar = float(last.close) > float(prev.close)
            if direction == TrendDirection.BULLISH and not bull_bar:
                return MicroEntryResult(
                    False,
                    "5m يتعارض مع اتجاه 4H/1H (شمعة هابطة قبل دخول شراء)",
                )
            if direction == TrendDirection.BEARISH and bull_bar:
                return MicroEntryResult(
                    False,
                    "5m يتعارض مع اتجاه 4H/1H (شمعة صاعدة قبل دخول بيع)",
                )
            notes.append("5m متسق")

        if c1 and len(c1) >= 8:
            ranges = [
                abs(float(c.high) - float(c.low))
                for c in c1[-8:]
                if float(c.high) > 0 and float(c.low) >= 0
            ]
            if ranges:
                last_range = ranges[-1]
                median = sorted(ranges)[len(ranges) // 2] or 1e-9
                # انزلاق عنيف: مدى الشمعة الأخيرة > 3× الوسيط
                if last_range > 3.0 * median and median > 0:
                    return MicroEntryResult(
                        False,
                        f"انزلاق 1m مرتفع (range={last_range:.6g} > 3×median)",
                    )
                notes.append("1m انزلاق مقبول")

        return MicroEntryResult(True, " | ".join(notes) if notes else "مجهري OK")
    except Exception as exc:  # noqa: BLE001
        # Fail-soft هنا فقط لأن نقص 5m/1m لا يجب أن يوقف التحليل الهرمي
        return MicroEntryResult(True, f"مجهري تخطي: {exc}")
