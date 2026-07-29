from __future__ import annotations

from data.cache_manager import get_cache_manager
from data.connection_utils import fetch_with_retry
from data.exchange_client import get_exchange
from data.models.orderbook import OrderBook


class OrderBookFetcher:
    """جلب دفتر الأوامر لتحليل السيولة."""

    def __init__(self, cache_ttl_seconds: int = 10) -> None:
        self._cache = get_cache_manager()
        self._cache_ttl = cache_ttl_seconds

    def fetch(
        self,
        symbol: str,
        *,
        depth: int = 20,
        use_cache: bool = True,
    ) -> OrderBook:
        cache_key = f"orderbook:{symbol}:{depth}"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        def _fetch() -> OrderBook:
            exchange = get_exchange()
            raw = exchange.fetch_order_book(symbol, limit=depth)
            return OrderBook.from_ccxt(symbol, raw, depth=depth)

        orderbook = fetch_with_retry(
            _fetch,
            operation_name=f"fetch_order_book({symbol})",
        )

        if use_cache:
            self._cache.set(cache_key, orderbook, ttl_seconds=self._cache_ttl)

        return orderbook
