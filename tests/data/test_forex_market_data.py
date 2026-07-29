"""اختبارات مصدر الفوركس — MT5 أولاً."""

from __future__ import annotations

from data.forex_market_data import fetch_forex_ohlcv, fetch_forex_ticker
from data.models.candle import Candle
from data.models.ticker import Ticker


def test_forex_uses_mt5_first(monkeypatch):
    candles = [
        Candle(timestamp=1_700_000_000_000, open=1.1, high=1.2, low=1.0, close=1.15, volume=0.0)
    ]
    monkeypatch.setattr("data.mt5_market_data.fetch_mt5_ohlcv", lambda *_a, **_k: candles)

    def boom(*_a, **_k):
        raise RuntimeError("should not call yahoo first")

    monkeypatch.setattr("data.forex_market_data._from_yahoo_chart", boom)
    result = fetch_forex_ohlcv("FOREX/EURUSD", "15m", limit=50)
    assert result == candles


def test_forex_falls_back_to_yahoo_when_mt5_fails(monkeypatch):
    def mt5_boom(*_a, **_k):
        raise RuntimeError("mt5 down")

    monkeypatch.setattr("data.mt5_market_data.fetch_mt5_ohlcv", mt5_boom)

    candles = [
        Candle(timestamp=1_700_000_000_000, open=1.1, high=1.2, low=1.0, close=1.15, volume=0.0)
    ]
    monkeypatch.setattr("data.forex_market_data._from_yahoo_chart", lambda *_a, **_k: candles)

    result = fetch_forex_ohlcv("FOREX/EURUSD", "15m", limit=50)
    assert result == candles


def test_forex_ticker_uses_mt5_first(monkeypatch):
    expected = Ticker(
        symbol="FOREX/EURUSD",
        last=1.08,
        bid=1.08,
        ask=1.08,
        spread=0.0,
        spread_pct=0.0,
        timestamp=None,
    )
    monkeypatch.setattr("data.mt5_market_data.fetch_mt5_ticker", lambda *_a, **_k: expected)
    result = fetch_forex_ticker("FOREX/EURUSD")
    assert result.last == 1.08
