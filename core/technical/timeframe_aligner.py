from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.constants import SMA_PERIOD, TIMEFRAMES
from core.technical.indicators import closes, sma
from data.models.candle import Candle


class TrendDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class TimeframeAlignment:
    aligned: bool
    direction: TrendDirection
    per_timeframe: dict[str, TrendDirection]


def _timeframe_direction(candles: list[Candle]) -> TrendDirection:
    close_values = closes(candles)
    sma_value = sma(close_values, SMA_PERIOD)
    if sma_value is None:
        return TrendDirection.NEUTRAL

    last_close = close_values[-1]
    if last_close > sma_value:
        return TrendDirection.BULLISH
    if last_close < sma_value:
        return TrendDirection.BEARISH
    return TrendDirection.NEUTRAL


def align_timeframes(
    candles_by_timeframe: dict[str, list[Candle]],
    *,
    required_timeframes: tuple[str, ...] = TIMEFRAMES,
) -> TimeframeAlignment:
    per_timeframe: dict[str, TrendDirection] = {}

    for timeframe in required_timeframes:
        candles = candles_by_timeframe.get(timeframe, [])
        per_timeframe[timeframe] = _timeframe_direction(candles)

    directions = set(per_timeframe.values())
    directions.discard(TrendDirection.NEUTRAL)

    if len(directions) != 1:
        return TimeframeAlignment(
            aligned=False,
            direction=TrendDirection.NEUTRAL,
            per_timeframe=per_timeframe,
        )

    direction = directions.pop()
    return TimeframeAlignment(
        aligned=True,
        direction=direction,
        per_timeframe=per_timeframe,
    )
