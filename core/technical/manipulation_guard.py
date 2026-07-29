from __future__ import annotations

from dataclasses import dataclass

from core.technical.indicators import candle_body, lower_wick, upper_wick
from data.models.candle import Candle


@dataclass(frozen=True)
class ManipulationGuardResult:
    is_suspicious: bool
    reason: str
    stop_hunt_detected: bool


def _recent_low(candles: list[Candle], lookback: int = 8) -> float:
    window = candles[-lookback:]
    return min(candle.low for candle in window)


def detect_manipulation(candles: list[Candle]) -> ManipulationGuardResult:
    if len(candles) < 6:
        return ManipulationGuardResult(
            is_suspicious=False,
            reason="بيانات غير كافية",
            stop_hunt_detected=False,
        )

    last = candles[-1]
    body = candle_body(last)
    lower = lower_wick(last)
    upper = upper_wick(last)

    recent_low = _recent_low(candles[:-1], lookback=8)

    # Stop Hunt صاعد: ذيل سفلي طويل يخترق قاعاً حديثاً ثم إغلاق أعلى من الافتتاح
    bullish_stop_hunt = (
        lower > body * 1.5
        and last.low < recent_low
        and last.close > last.open
        and lower > upper
    )

    # Stop Hunt هابط: ذيل علوي طويل يخترق قمة حديثة ثم إغلاق أسفل الافتتاح
    recent_high = max(candle.high for candle in candles[-9:-1])
    bearish_stop_hunt = (
        upper > body * 1.5
        and last.high > recent_high
        and last.close < last.open
        and upper > lower
    )

    if bullish_stop_hunt or bearish_stop_hunt:
        return ManipulationGuardResult(
            is_suspicious=True,
            reason="تم رصد Stop Hunt — شمعة خادعة",
            stop_hunt_detected=True,
        )

    return ManipulationGuardResult(
        is_suspicious=False,
        reason="لا تلاعب واضح",
        stop_hunt_detected=False,
    )
