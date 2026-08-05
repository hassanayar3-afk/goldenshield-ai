"""توجيه الرموز — Binance كريبتو؛ فوركس/أسهم غير مدعومة للتنفيذ."""

from __future__ import annotations

_FOREX_MAJORS = frozenset(
    {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "USDCHF",
        "NZDUSD",
        "EURGBP",
        "EURJPY",
        "GBPJPY",
        # معادن وطاقة
        "XAUUSD",
        "XAGUSD",
        "USOIL",
        "UKOIL",
        "GOLD",
        "SILVER",
    }
)

_COMMODITY_CANONICAL = {
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "WTI": "USOIL",
    "CL": "USOIL",
    "XTIUSD": "USOIL",
}


def normalize_symbol_id(symbol: str) -> str:
    raw = (symbol or "").strip()
    upper = raw.upper()
    if upper.startswith("FOREX/"):
        pair = upper.split("/", 1)[1].replace("/", "").replace("-", "")
        pair = _COMMODITY_CANONICAL.get(pair, pair)
        return f"FOREX/{pair}"
    if upper.startswith("STOCK/"):
        return f"STOCK/{upper.split('/', 1)[1]}"
    compact = upper.replace("/", "").replace("-", "")
    compact = _COMMODITY_CANONICAL.get(compact, compact)
    if compact in _FOREX_MAJORS or compact in {"XAUUSD", "XAGUSD", "USOIL", "UKOIL"}:
        return f"FOREX/{compact}"
    return raw


def infer_data_source(symbol: str) -> str:
    """يستنتج المصدر من المعرّف — الكريبتو → binance؛ غير ذلك يُرفض عند الجلب."""
    sid = normalize_symbol_id(symbol)
    if sid.startswith("FOREX/"):
        return "unsupported"
    if sid.startswith("STOCK/"):
        return "unsupported"
    try:
        from operations.symbol_registry import get_symbol_registry

        spec = get_symbol_registry().get(sid) or get_symbol_registry().get(symbol)
        if spec is not None and spec.data_source:
            src = str(spec.data_source).strip().lower()
            if src in {"forex", "yfinance", "mt5", "stock"}:
                return "unsupported"
            return src if src else "binance"
    except Exception:
        pass
    return "binance"


def display_symbol(symbol: str) -> str:
    """اسم عرض للإشارات — بدون FOREX/USDT الخاطئ."""
    sid = normalize_symbol_id(symbol)
    if sid.startswith("FOREX/"):
        return sid.split("/", 1)[1]
    if sid.startswith("STOCK/"):
        return sid.split("/", 1)[1]
    if "/USDT" in sid.upper():
        return sid.split("/", 1)[0]
    return sid


def format_price(symbol: str, price: float) -> str:
    sid = normalize_symbol_id(symbol)
    if sid.startswith("FOREX/"):
        pair = sid.split("/", 1)[1]
        if pair in {"XAUUSD", "XAGUSD", "USOIL", "UKOIL"}:
            return f"{price:,.2f}"
        if pair.endswith("JPY"):
            return f"{price:.3f}"
        return f"{price:.5f}"
    if sid.startswith("STOCK/"):
        return f"{price:.2f}"
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 1:
        return f"{price:.4f}"
    return f"{price:.6f}"
