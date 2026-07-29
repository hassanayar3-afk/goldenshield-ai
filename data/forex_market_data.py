"""بيانات الفوركس — سلسلة مصادر موثوقة للتحليل (التنفيذ يبقى MT5)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from data.models.candle import Candle
from data.models.ticker import Ticker

logger = logging.getLogger(__name__)

_YF_INTERVAL = {
    "15m": "15m",
    "1h": "60m",
    "4h": "60m",
    "1d": "1d",
}

_YF_RANGE = {
    "15m": "5d",
    "1h": "1mo",
    "4h": "1mo",
    "1d": "3mo",
}

_YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

_YAHOO_HOSTS = (
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com",
)


def _pair_code(symbol_id: str) -> str:
    return symbol_id.upper().replace("FOREX/", "").replace("/", "").replace("-", "")


def _yahoo_ticker(symbol_id: str) -> str:
    from operations.symbol_registry import get_symbol_registry

    spec = get_symbol_registry().get(symbol_id)
    if spec and spec.yfinance_ticker:
        return spec.yfinance_ticker
    return f"{_pair_code(symbol_id)}=X"


def _base_quote(symbol_id: str) -> tuple[str, str]:
    code = _pair_code(symbol_id)
    commodity = {
        "XAUUSD": ("XAU", "USD"),
        "XAGUSD": ("XAG", "USD"),
        "USOIL": ("WTI", "USD"),
        "UKOIL": ("BRENT", "USD"),
        "GOLD": ("XAU", "USD"),
        "SILVER": ("XAG", "USD"),
    }
    if code in commodity:
        return commodity[code]
    if len(code) != 6:
        raise ValueError(f"زوج فوركس غير معروف: {symbol_id}")
    return code[:3], code[3:]


def _aggregate_4h(candles: list[Candle]) -> list[Candle]:
    """تجميع ساعة → 4 ساعات بمحاذاة ساعة الجدار (ليس كل 4 شموع متتالية)."""
    if not candles:
        return []
    step = 4 * 60 * 60 * 1000
    buckets: dict[int, list[Candle]] = {}
    for candle in candles:
        key = int(candle.timestamp) - (int(candle.timestamp) % step)
        buckets.setdefault(key, []).append(candle)
    out: list[Candle] = []
    for key in sorted(buckets):
        chunk = buckets[key]
        out.append(
            Candle(
                timestamp=key,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=sum(c.volume for c in chunk),
            )
        )
    return out


def _from_yahoo_chart(symbol_id: str, timeframe: str, *, limit: int) -> list[Candle]:
    interval = _YF_INTERVAL.get(timeframe)
    range_ = _YF_RANGE.get(timeframe)
    if interval is None or range_ is None:
        raise ValueError(f"إطار فوركس غير مدعوم: {timeframe}")

    ticker = _yahoo_ticker(symbol_id)
    last_error: Exception | None = None
    payload: dict[str, Any] | None = None
    for host in _YAHOO_HOSTS:
        try:
            response = requests.get(
                f"{host}/v8/finance/chart/{ticker}",
                params={"interval": interval, "range": range_},
                headers=_YAHOO_HEADERS,
                timeout=12,
            )
            response.raise_for_status()
            payload = response.json()
            break
        except Exception as exc:
            last_error = exc
            continue
    if payload is None:
        raise RuntimeError(f"Yahoo chart فشل لـ {symbol_id}: {last_error}")

    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(f"لا بيانات Yahoo لفوركس {symbol_id}")

    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    candles: list[Candle] = []
    for idx, ts in enumerate(timestamps):
        close = closes[idx] if idx < len(closes) else None
        if close is None:
            continue
        candles.append(
            Candle(
                timestamp=int(ts) * 1000,
                open=float(opens[idx] if idx < len(opens) and opens[idx] is not None else close),
                high=float(highs[idx] if idx < len(highs) and highs[idx] is not None else close),
                low=float(lows[idx] if idx < len(lows) and lows[idx] is not None else close),
                close=float(close),
                volume=float(volumes[idx] or 0.0) if idx < len(volumes) else 0.0,
            )
        )

    if not candles:
        raise RuntimeError(f"شموع Yahoo فارغة لـ {symbol_id}")

    if timeframe == "4h":
        candles = _aggregate_4h(candles)
    return candles[-limit:]


def _ticker_from_yahoo(symbol_id: str) -> Ticker:
    candles = _from_yahoo_chart(symbol_id, "15m", limit=5)
    last = candles[-1].close
    return Ticker(
        symbol=symbol_id,
        last=last,
        bid=last,
        ask=last,
        spread=0.0,
        spread_pct=None,  # مصدر احتياط — لا ندّعي سبريد حقيقي
        timestamp=candles[-1].timestamp,
    )


def _spot_from_er_api(symbol_id: str) -> float:
    base, quote = _base_quote(symbol_id)
    response = requests.get(
        f"https://open.er-api.com/v6/latest/{base}",
        timeout=10,
        headers=_YAHOO_HEADERS,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("result") != "success":
        raise RuntimeError(f"er-api فشل لـ {symbol_id}")
    rates = payload.get("rates") or {}
    rate = rates.get(quote)
    if rate is None:
        raise RuntimeError(f"لا سعر {base}/{quote} من er-api")
    return float(rate)


def _candles_from_spot(symbol_id: str, timeframe: str, *, limit: int, spot: float) -> list[Candle]:
    """شموع طارئة من سعر لحظي — فقط إذا فشلت كل المصادر التاريخية."""
    import time

    step_ms = {"15m": 15 * 60_000, "1h": 60 * 60_000, "4h": 4 * 60 * 60_000, "1d": 24 * 60 * 60_000}[
        timeframe
    ]
    now = int(time.time() * 1000)
    candles: list[Candle] = []
    for i in range(limit, 0, -1):
        ts = now - i * step_ms
        candles.append(
            Candle(
                timestamp=ts,
                open=spot,
                high=spot,
                low=spot,
                close=spot,
                volume=0.0,
            )
        )
    return candles


def fetch_forex_ohlcv(symbol_id: str, timeframe: str, *, limit: int) -> list[Candle]:
    errors: list[str] = []

    # 1) MT5 أولاً — نفس أسعار XM المستخدمة للتنفيذ
    try:
        from data.mt5_market_data import fetch_mt5_ohlcv

        candles = fetch_mt5_ohlcv(symbol_id, timeframe, limit=limit)
        if candles:
            logger.info("forex OHLCV %s via MT5 (%s bars)", symbol_id, len(candles))
            return candles
        errors.append("mt5:empty")
    except Exception as exc:
        errors.append(f"mt5:{exc}")
        logger.warning("forex MT5 OHLCV failed for %s: %s", symbol_id, exc)

    # 2) Yahoo احتياط
    try:
        candles = _from_yahoo_chart(symbol_id, timeframe, limit=limit)
        logger.info("forex OHLCV %s via Yahoo (%s bars)", symbol_id, len(candles))
        return candles
    except Exception as exc:
        errors.append(f"yahoo:{exc}")
        logger.warning("forex Yahoo OHLCV failed for %s: %s", symbol_id, exc)

    # 3) yfinance احتياط أخير
    try:
        from data.stock_market_data import fetch_stock_ohlcv

        candles = fetch_stock_ohlcv(symbol_id, timeframe, limit=limit)
        logger.info("forex OHLCV %s via yfinance (%s bars)", symbol_id, len(candles))
        return candles
    except Exception as exc:
        errors.append(f"yfinance:{exc}")
        logger.warning("forex yfinance OHLCV failed for %s: %s", symbol_id, exc)

    # لا شموع مسطّحة في live — فشل صريح أفضل من إشارة وهمية
    raise RuntimeError(f"فشل جلب فوركس {symbol_id}: {' | '.join(errors)}")


def fetch_forex_ticker(symbol_id: str) -> Ticker:
    errors: list[str] = []

    try:
        from data.mt5_market_data import fetch_mt5_ticker

        ticker = fetch_mt5_ticker(symbol_id)
        if ticker.last > 0:
            logger.info("forex ticker %s via MT5 @ %s", symbol_id, ticker.last)
            return ticker
        errors.append("mt5:empty")
    except Exception as exc:
        errors.append(f"mt5:{exc}")
        logger.warning("forex MT5 ticker failed for %s: %s", symbol_id, exc)

    try:
        ticker = _ticker_from_yahoo(symbol_id)
        logger.info("forex ticker %s via Yahoo @ %s", symbol_id, ticker.last)
        return ticker
    except Exception as exc:
        errors.append(f"yahoo:{exc}")
        logger.warning("forex Yahoo ticker failed for %s: %s", symbol_id, exc)

    try:
        from data.stock_market_data import fetch_stock_ticker

        ticker = fetch_stock_ticker(symbol_id)
        logger.info("forex ticker %s via yfinance @ %s", symbol_id, ticker.last)
        return ticker
    except Exception as exc:
        errors.append(f"yfinance:{exc}")
        logger.warning("forex yfinance ticker failed for %s: %s", symbol_id, exc)

    try:
        spot = _spot_from_er_api(symbol_id)
        logger.warning("forex ticker %s via er-api @ %s", symbol_id, spot)
        return Ticker(
            symbol=symbol_id,
            last=spot,
            bid=spot,
            ask=spot,
            spread=0.0,
            spread_pct=None,
            timestamp=None,
        )
    except Exception as exc:
        errors.append(f"er-api:{exc}")
        logger.warning("forex er-api ticker failed for %s: %s", symbol_id, exc)

    raise RuntimeError(f"فشل سعر فوركس {symbol_id}: {' | '.join(errors)}")
