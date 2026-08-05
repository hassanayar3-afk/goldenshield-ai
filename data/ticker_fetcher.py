from __future__ import annotations

from data.cache_manager import get_cache_manager
from data.connection_utils import fetch_with_retry
from data.exchange_client import get_exchange
from data.models.ticker import Ticker
from data.symbol_routing import infer_data_source


class TickerFetcher:
    """جلب السعر اللحظي من Binance (كريبتو فقط)."""

    def __init__(self, cache_ttl_seconds: int = 5) -> None:
        self._cache = get_cache_manager()
        self._cache_ttl = cache_ttl_seconds

    def fetch(self, symbol: str, *, use_cache: bool = True) -> Ticker:
        source = infer_data_source(symbol)
        if source != "binance":
            raise ValueError(
                f"مصدر غير مدعوم لـ {symbol}: {source}. "
                "GoldenShield يعمل على Binance (كريبتو) فقط."
            )

        cache_key = f"ticker:{source}:{symbol}"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        def _fetch() -> Ticker:
            exchange = get_exchange()
            raw = exchange.fetch_ticker(symbol)
            return Ticker.from_ccxt(symbol, raw)

        ticker = fetch_with_retry(
            _fetch,
            max_retries=3,
            base_delay=0.5,
            operation_name=f"fetch_ticker({symbol})",
        )

        if use_cache:
            self._cache.set(cache_key, ticker, ttl_seconds=self._cache_ttl)

        return ticker
