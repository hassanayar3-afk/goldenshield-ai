from data.models.candle import Candle


def make_candle(
    index: int,
    *,
    open_price: float,
    close: float,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000.0,
) -> Candle:
    return Candle(
        timestamp=index * 60_000,
        open=open_price,
        high=high if high is not None else max(open_price, close) + 1,
        low=low if low is not None else min(open_price, close) - 1,
        close=close,
        volume=volume,
    )


def bullish_trend_series(length: int = 55, start: float = 100.0) -> list[Candle]:
    candles: list[Candle] = []
    price = start
    for index in range(length):
        open_price = price
        close = price + 2
        candles.append(
            make_candle(
                index,
                open_price=open_price,
                close=close,
                high=close + 1,
                low=open_price - 0.5,
            )
        )
        price = close
    return candles


def zigzag_series(cycles: int = 6, base: float = 100.0) -> list[Candle]:
    candles: list[Candle] = []
    index = 0
    price = base
    for cycle in range(cycles):
        # صعود
        for _ in range(4):
            open_price = price
            close = price + 3
            candles.append(
                make_candle(
                    index,
                    open_price=open_price,
                    close=close,
                    high=close + 1,
                    low=open_price - 0.5,
                )
            )
            price = close
            index += 1
        # هبوط
        for _ in range(4):
            open_price = price
            close = price - 2
            candles.append(
                make_candle(
                    index,
                    open_price=open_price,
                    close=close,
                    high=open_price + 0.5,
                    low=close - 1,
                )
            )
            price = close
            index += 1
    return candles


def bearish_reversal_last_candle(candles: list[Candle]) -> list[Candle]:
    """إضافة شمعة Stop Hunt صاعدة."""
    last_close = candles[-1].close
    return [
        *candles,
        make_candle(
            len(candles),
            open_price=last_close,
            close=last_close + 3,
            high=last_close + 4,
            low=last_close - 15,
            volume=5000,
        ),
    ]
