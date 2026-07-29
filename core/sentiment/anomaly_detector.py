from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from data.models.candle import Candle


@dataclass(frozen=True)
class AnomalyResult:
    detected: bool
    price_change_pct: float
    volume_change_pct: float
    divergence_ratio: float
    reason: str


def detect_sentiment_anomaly(candles: list[Candle], *, lookback: int = 5) -> AnomalyResult:
    settings = get_settings()

    if len(candles) < lookback + 1:
        return AnomalyResult(
            detected=False,
            price_change_pct=0.0,
            volume_change_pct=0.0,
            divergence_ratio=0.0,
            reason="بيانات غير كافية",
        )

    recent = candles[-lookback:]
    first = recent[0]
    last = recent[-1]

    if first.close <= 0:
        return AnomalyResult(False, 0.0, 0.0, 0.0, "سعر غير صالح")

    price_change_pct = ((last.close - first.close) / first.close) * 100
    avg_early_volume = sum(candle.volume for candle in recent[: lookback // 2]) / max(1, lookback // 2)
    avg_late_volume = sum(candle.volume for candle in recent[lookback // 2 :]) / max(1, lookback - lookback // 2)

    if avg_early_volume <= 0:
        volume_change_pct = 0.0
    else:
        volume_change_pct = ((avg_late_volume - avg_early_volume) / avg_early_volume) * 100

    divergence_ratio = abs(price_change_pct) / max(abs(volume_change_pct), 0.01)
    detected = (
        abs(price_change_pct) >= 1.0
        and divergence_ratio >= settings.sentiment_anomaly_threshold
        and price_change_pct * volume_change_pct < 0
    )

    if detected:
        reason = (
            f"تلاعب محتمل: السعر {price_change_pct:+.2f}% "
            f"مقابل الحجم {volume_change_pct:+.2f}%"
        )
    else:
        reason = "لا انحراف سعر/حجم"

    return AnomalyResult(
        detected=detected,
        price_change_pct=price_change_pct,
        volume_change_pct=volume_change_pct,
        divergence_ratio=divergence_ratio,
        reason=reason,
    )
