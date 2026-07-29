from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from data.models.candle import Candle


class MarketStructure(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class SMCResult:
    structure: MarketStructure
    bos: bool
    choch: bool
    order_block: bool
    swing_high: float | None
    swing_low: float | None


def _is_swing_high(candles: list[Candle], index: int, lookback: int) -> bool:
    pivot_high = candles[index].high
    for offset in range(1, lookback + 1):
        if candles[index - offset].high >= pivot_high:
            return False
        if candles[index + offset].high >= pivot_high:
            return False
    return True


def _is_swing_low(candles: list[Candle], index: int, lookback: int) -> bool:
    pivot_low = candles[index].low
    for offset in range(1, lookback + 1):
        if candles[index - offset].low <= pivot_low:
            return False
        if candles[index + offset].low <= pivot_low:
            return False
    return True


def _latest_swings(candles: list[Candle], lookback: int = 2) -> tuple[float | None, float | None]:
    if len(candles) < (lookback * 2) + 3:
        return None, None

    swing_highs: list[float] = []
    swing_lows: list[float] = []

    for index in range(lookback, len(candles) - lookback):
        if _is_swing_high(candles, index, lookback):
            swing_highs.append(candles[index].high)
        if _is_swing_low(candles, index, lookback):
            swing_lows.append(candles[index].low)

    return (swing_highs[-1] if swing_highs else None, swing_lows[-1] if swing_lows else None)


def _has_bullish_order_block(candles: list[Candle]) -> bool:
    if len(candles) < 4:
        return False

    last = candles[-1]
    previous = candles[-2]
    if last.close <= last.open:
        return False
    if previous.close >= previous.open:
        return False

    impulse = last.close - previous.open
    return impulse > 0


def analyze_smc(candles: list[Candle], lookback: int = 2) -> SMCResult:
    if len(candles) < 8:
        return SMCResult(
            structure=MarketStructure.NEUTRAL,
            bos=False,
            choch=False,
            order_block=False,
            swing_high=None,
            swing_low=None,
        )

    swing_high, swing_low = _latest_swings(candles, lookback=lookback)
    last_close = candles[-1].close
    prev_close = candles[-2].close

    bos = False
    choch = False
    structure = MarketStructure.NEUTRAL

    if swing_high is not None and last_close > swing_high:
        bos = True
        structure = MarketStructure.BULLISH
    elif swing_low is not None and last_close < swing_low:
        bos = True
        structure = MarketStructure.BEARISH

    if swing_high is not None and prev_close > swing_high and last_close < swing_high:
        choch = True
        structure = MarketStructure.BEARISH
    elif swing_low is not None and prev_close < swing_low and last_close > swing_low:
        choch = True
        structure = MarketStructure.BULLISH

    order_block = _has_bullish_order_block(candles)

    return SMCResult(
        structure=structure,
        bos=bos,
        choch=choch,
        order_block=order_block,
        swing_high=swing_high,
        swing_low=swing_low,
    )
