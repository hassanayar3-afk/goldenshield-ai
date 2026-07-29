from __future__ import annotations

from data.cache_manager import get_cache_manager
from data.connection_utils import fetch_with_retry
from data.exchange_client import get_exchange
from data.models.ticker import Ticker
from data.symbol_routing import infer_data_source


class TickerFetcher:
    """جلب السعر اللحظي — Binance أو MT5 أو yfinance."""

    def __init__(self, cache_ttl_seconds: int = 5) -> None:
        self._cache = get_cache_manager()
        self._cache_ttl = cache_ttl_seconds

    def fetch(self, symbol: str, *, use_cache: bool = True) -> Ticker:
        cache_key = f"ticker:{infer_data_source(symbol)}:{symbol}"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        source = infer_data_source(symbol)

        def _fetch() -> Ticker:
            if source == "forex":
                from data.forex_market_data import fetch_forex_ticker

                return fetch_forex_ticker(symbol)
            if source == "yfinance":
                from data.stock_market_data import fetch_stock_ticker

                return fetch_stock_ticker(symbol)
            if source == "mt5":
                from data.mt5_market_data import fetch_mt5_ticker

                return fetch_mt5_ticker(symbol)
            exchange = get_exchange()
            raw = exchange.fetch_ticker(symbol)
            return Ticker.from_ccxt(symbol, raw)

        retries = 3 if source == "binance" else 1
        ticker = fetch_with_retry(
            _fetch,
            max_retries=retries,
            base_delay=0.5,
            operation_name=f"fetch_ticker({symbol})",
        )

        if use_cache:
            self._cache.set(cache_key, ticker, ttl_seconds=self._cache_ttl)

        return ticker
