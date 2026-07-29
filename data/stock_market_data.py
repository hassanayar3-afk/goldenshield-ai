"""بيانات الأسهم عبر yfinance — للتحليل أثناء التنفيذ على MT5."""

from __future__ import annotations

from data.models.candle import Candle
from data.models.ticker import Ticker

_YF_INTERVAL = {
    "15m": "15m",
    "1h": "1h",
    "4h": "1h",
    "1d": "1d",
}


def _ticker_for(symbol_id: str) -> str:
    from operations.symbol_registry import get_symbol_registry

    spec = get_symbol_registry().get(symbol_id)
    if spec and spec.yfinance_ticker:
        return spec.yfinance_ticker
    if symbol_id.startswith("FOREX/"):
        pair = symbol_id.split("/", 1)[1]
        return f"{pair}=X"
    return symbol_id.split("/", 1)[-1]


def fetch_stock_ohlcv(symbol_id: str, timeframe: str, *, limit: int) -> list[Candle]:
    import yfinance as yf

    interval = _YF_INTERVAL.get(timeframe)
    if interval is None:
        raise ValueError(f"إطار yfinance غير مدعوم: {timeframe}")

    ticker = yf.Ticker(_ticker_for(symbol_id))
    period = "5d" if timeframe in {"15m", "1h"} else "1mo"
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        raise RuntimeError(f"لا بيانات yfinance لـ {symbol_id}")

    rows = df.tail(limit)
    candles: list[Candle] = []
    for ts, row in rows.iterrows():
        candles.append(
            Candle(
                timestamp=int(ts.timestamp() * 1000),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0.0) or 0.0),
            )
        )
    if timeframe == "4h" and interval == "1h":
        candles = _aggregate_4h(candles)[-limit:]
    return candles


def _aggregate_4h(candles: list[Candle]) -> list[Candle]:
    if not candles:
        return []
    buckets: list[Candle] = []
    chunk: list[Candle] = []
    for candle in candles:
        chunk.append(candle)
        if len(chunk) == 4:
            buckets.append(
                Candle(
                    timestamp=chunk[0].timestamp,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=sum(c.volume for c in chunk),
                )
            )
            chunk = []
    return buckets


def fetch_stock_ticker(symbol_id: str) -> Ticker:
    import yfinance as yf

    ticker = yf.Ticker(_ticker_for(symbol_id))
    info = ticker.fast_info
    last = float(getattr(info, "last_price", 0.0) or 0.0)
    if last <= 0:
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            raise RuntimeError(f"لا سعر yfinance لـ {symbol_id}")
        last = float(hist["Close"].iloc[-1])
    return Ticker(
        symbol=symbol_id,
        last=last,
        bid=last,
        ask=last,
        spread=0.0,
        spread_pct=0.0,
        timestamp=None,
    )
