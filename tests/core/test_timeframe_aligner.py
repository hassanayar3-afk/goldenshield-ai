from core.technical.timeframe_aligner import TrendDirection, align_timeframes
from tests.core.helpers import bullish_trend_series


def test_timeframes_aligned_bullish():
    candles = bullish_trend_series(length=55)
    candles_by_tf = {
        "15m": candles,
        "1h": candles,
        "4h": candles,
    }

    result = align_timeframes(candles_by_tf)
    assert result.aligned is True
    assert result.direction == TrendDirection.BULLISH


def test_timeframes_not_aligned_when_mixed():
    bullish = bullish_trend_series(length=55)
    bearish = list(reversed([*bullish]))
    for index, candle in enumerate(bearish):
        bearish[index] = candle

    # اتجاه هابط صناعي
    falling = []
    price = 200.0
    for index in range(55):
        falling.append(
            type(bullish[0])(
                timestamp=index,
                open=price,
                high=price + 1,
                low=price - 3,
                close=price - 2,
                volume=1000,
            )
        )
        price -= 2

    result = align_timeframes({"15m": bullish, "1h": bullish, "4h": falling})
    assert result.aligned is False
    assert result.direction == TrendDirection.NEUTRAL
