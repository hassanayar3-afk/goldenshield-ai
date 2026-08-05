"""توجيه الرموز — Binance كريبتو فقط."""

from __future__ import annotations

_CRYPTO_QUOTES = frozenset({"USDT", "USDC", "BUSD", "BTC", "ETH", "FDUSD"})

# رموز غير كريبتو شائعة — تُرفض دائماً
_REJECT_COMPACT = frozenset(
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
        "XAUUSD",
        "XAGUSD",
        "USOIL",
        "UKOIL",
        "GOLD",
        "SILVER",
        "AAPL",
        "TSLA",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
    }
)


def normalize_symbol_id(symbol: str) -> str:
    raw = (symbol or "").strip()
    if not raw:
        return raw
    upper = raw.upper().replace("-", "/")
    if upper.startswith(("FOREX/", "STOCK/")):
        return upper
    if "/" not in upper and upper.endswith("USDT") and len(upper) > 4:
        return f"{upper[:-4]}/USDT"
    return upper


def is_binance_crypto_pair(symbol: str) -> bool:
    sid = normalize_symbol_id(symbol)
    if not sid or sid.startswith(("FOREX/", "STOCK/")):
        return False
    compact = sid.replace("/", "")
    if compact in _REJECT_COMPACT:
        return False
    if "/" not in sid:
        return False
    base, quote = sid.split("/", 1)
    if not base or quote not in _CRYPTO_QUOTES:
        return False
    if base in _REJECT_COMPACT:
        return False
    # رفض فوركس مموّه مثل EURUSD/USDT
    if len(base) == 6 and base.isalpha() and base.endswith("USD"):
        return False
    if len(base) == 6 and base.isalpha() and base.startswith("USD"):
        return False
    return base.isalnum()


def infer_data_source(symbol: str) -> str:
    """مصدر البيانات الوحيد المسموح: binance. غير ذلك unsupported."""
    if is_binance_crypto_pair(symbol):
        return "binance"
    return "unsupported"


def display_symbol(symbol: str) -> str:
    sid = normalize_symbol_id(symbol)
    if sid.startswith(("FOREX/", "STOCK/")):
        return sid.split("/", 1)[1]
    if "/" in sid:
        return sid.split("/", 1)[0]
    return sid


def format_price(symbol: str, price: float) -> str:
    """تنسيق سعر كريبتو Binance."""
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 1:
        return f"{price:.4f}"
    return f"{price:.6f}"
