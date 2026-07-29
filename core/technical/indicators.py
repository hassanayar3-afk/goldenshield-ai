from __future__ import annotations

from data.models.candle import Candle


def closes(candles: list[Candle]) -> list[float]:
    return [candle.close for candle in candles]


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period or period < 1:
        return None
    window = values[-period:]
    return sum(window) / period


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None

    gains = 0.0
    losses = 0.0
    for index in range(-period, 0):
        change = values[index] - values[index - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change

    if losses == 0:
        return 100.0

    rs = gains / losses
    return 100 - (100 / (1 + rs))


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None

    true_ranges: list[float] = []
    for index in range(-period, 0):
        current = candles[index]
        previous = candles[index - 1]
        tr = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        true_ranges.append(tr)

    return sum(true_ranges) / len(true_ranges)


def adx(candles: list[Candle], period: int = 14) -> float | None:
    """Average Directional Index — طبقة مضافة للفلاتر المؤسسية."""
    try:
        if period < 1 or len(candles) < period * 2 + 1:
            return None
        plus_dm: list[float] = []
        minus_dm: list[float] = []
        tr_list: list[float] = []
        for i in range(1, len(candles)):
            cur = candles[i]
            prev = candles[i - 1]
            up = cur.high - prev.high
            down = prev.low - cur.low
            plus_dm.append(up if up > down and up > 0 else 0.0)
            minus_dm.append(down if down > up and down > 0 else 0.0)
            tr_list.append(
                max(
                    cur.high - cur.low,
                    abs(cur.high - prev.close),
                    abs(cur.low - prev.close),
                )
            )
        if len(tr_list) < period:
            return None

        def _wilder(values: list[float], n: int) -> list[float]:
            if len(values) < n:
                return []
            out = [sum(values[:n])]
            for v in values[n:]:
                out.append(out[-1] - (out[-1] / n) + v)
            return out

        atr_s = _wilder(tr_list, period)
        plus_s = _wilder(plus_dm, period)
        minus_s = _wilder(minus_dm, period)
        if not atr_s or not plus_s or not minus_s:
            return None
        dx_vals: list[float] = []
        for a, p, m in zip(atr_s, plus_s, minus_s):
            if a <= 0:
                continue
            plus_di = 100.0 * (p / a)
            minus_di = 100.0 * (m / a)
            denom = plus_di + minus_di
            if denom <= 0:
                continue
            dx_vals.append(100.0 * abs(plus_di - minus_di) / denom)
        if len(dx_vals) < period:
            return None
        # ADX = متوسط DX
        return sum(dx_vals[-period:]) / period
    except Exception:
        return None


def candle_body(candle: Candle) -> float:
    return abs(candle.close - candle.open)


def lower_wick(candle: Candle) -> float:
    return min(candle.open, candle.close) - candle.low


def upper_wick(candle: Candle) -> float:
    return candle.high - max(candle.open, candle.close)
