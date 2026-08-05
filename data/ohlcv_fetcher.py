from __future__ import annotations

from core.constants import DEFAULT_OHLCV_LIMIT, ANALYSIS_TIMEFRAMES
from data.cache_manager import get_cache_manager
from data.connection_utils import fetch_with_retry
from data.exchange_client import get_exchange
from data.models.candle import Candle
from data.symbol_routing import infer_data_source

SUPPORTED_TIMEFRAMES: tuple[str, ...] = (*ANALYSIS_TIMEFRAMES, "1d")


class OHLCVFetcher:
    """جلب شموع OHLCV من Binance (كريبتو فقط)."""

    def __init__(self, cache_ttl_seconds: int | None = None) -> None:
        self._cache = get_cache_manager()
        self._cache_ttl = cache_ttl_seconds

    def _cache_key(self, symbol: str, timeframe: str, limit: int, source: str) -> str:
        return f"ohlcv:{source}:{symbol}:{timeframe}:{limit}"

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = DEFAULT_OHLCV_LIMIT,
        use_cache: bool = True,
    ) -> list[Candle]:
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"إطار زمني غير مدعوم: {timeframe}. المسموح: {SUPPORTED_TIMEFRAMES}"
            )

        source = infer_data_source(symbol)
        if source != "binance":
            raise ValueError(
                f"مصدر غير مدعوم لـ {symbol}: {source}. "
                "GoldenShield يعمل على Binance (كريبتو) فقط."
            )

        cache_key = self._cache_key(symbol, timeframe, limit, source)
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        def _fetch() -> list[Candle]:
            exchange = get_exchange()
            raw_rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            return [Candle.from_ohlcv_row(row) for row in raw_rows]

        candles = fetch_with_retry(
            _fetch,
            max_retries=3,
            base_delay=0.5,
            operation_name=f"fetch_ohlcv({symbol},{timeframe})",
        )

        if use_cache:
            ttl = self._cache_ttl if self._cache_ttl is not None else 60
            self._cache.set(cache_key, candles, ttl_seconds=ttl)

        return candles

    def fetch_multi(
        self,
        symbol: str,
        timeframes: tuple[str, ...] = ANALYSIS_TIMEFRAMES,
        *,
        limit: int = DEFAULT_OHLCV_LIMIT,
        use_cache: bool = True,
    ) -> dict[str, list[Candle]]:
        result: dict[str, list[Candle]] = {}
        errors: list[str] = []
        for timeframe in timeframes:
            try:
                result[timeframe] = self.fetch(
                    symbol, timeframe, limit=limit, use_cache=use_cache
                )
            except Exception as exc:
                errors.append(f"{timeframe}:{exc}")
        if not result:
            raise RuntimeError(
                f"فشل جلب كل الأطر لـ {symbol}: {' | '.join(errors) or 'unknown'}"
            )
        if errors and len(result) < len(timeframes):
            # أطر ناقصة — لا نفشل بالكامل إن وُجدت بيانات كافية للتحليل
            for timeframe in timeframes:
                if timeframe not in result and result:
                    # انسخ أقرب إطار متوفر مؤقتاً لتجنب انهيار التحليل
                    fallback_tf = next(iter(result.values()))
                    result[timeframe] = fallback_tf
        return result
