from core.technical.smc_analyzer import MarketStructure, analyze_smc
from tests.core.helpers import bullish_trend_series, make_candle, zigzag_series


def test_smc_detects_swings_in_zigzag_market():
    candles = zigzag_series(cycles=6)
    result = analyze_smc(candles)

    assert result.swing_high is not None
    assert result.swing_low is not None
    assert result.structure in {MarketStructure.BULLISH, MarketStructure.BEARISH, MarketStructure.NEUTRAL}


def test_smc_order_block_on_pullback_and_impulse():
    candles: list = []
    price = 100.0
    for index in range(10):
        candles.append(
            make_candle(index, open_price=price, close=price + 1, high=price + 2, low=price - 1)
        )
        price += 1

    candles.append(make_candle(10, open_price=price, close=price - 2, high=price, low=price - 3))
    candles.append(make_candle(11, open_price=price - 2, close=price + 4, high=price + 5, low=price - 3))

    result = analyze_smc(candles)
    assert result.order_block is True
