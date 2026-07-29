"""فلاتر سوق إضافية v1.3: BTC.D، Spoofing، MACD+RSI، Funding stub، Weekend flat."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _cfg() -> dict[str, Any]:
    raw = getattr(get_settings(), "institutional_v13", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _flag(key: str, default: bool = False) -> bool:
    cfg = _cfg()
    if key in cfg:
        return bool(cfg[key])
    return default


@dataclass(frozen=True)
class FilterResult:
    allowed: bool
    reason: str


# —— 12) BTC Dominance ——

_btc_dom_cache: tuple[float, float] | None = None  # (monotonic_ts, value)


def fetch_btc_dominance() -> float | None:
    """محاولة جلب هيمنة BTC — يفشل بهدوء."""
    global _btc_dom_cache
    import time

    now = time.monotonic()
    if _btc_dom_cache and now - _btc_dom_cache[0] < 300:
        return _btc_dom_cache[1]
    try:
        import requests

        resp = requests.get(
            "https://api.coingecko.com/api/v3/global",
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        dom = float(data["data"]["market_cap_percentage"]["btc"])
        _btc_dom_cache = (now, dom)
        return dom
    except Exception as exc:  # noqa: BLE001
        logger.debug("BTC dominance fetch failed: %s", exc)
        return None


def check_btc_dominance_filter(symbol: str, *, side: str = "buy") -> FilterResult:
    if not _flag("btc_dominance_filter_enabled", True):
        return FilterResult(True, "BTC.D filter معطّل")
    sym = symbol.upper().replace(":USDT", "").replace("/USDT", "")
    if sym.startswith("BTC") or sym in {"BTCUSDT", "BTC"}:
        return FilterResult(True, "BTC نفسه — لا فلتر هيمنة")

    dom = fetch_btc_dominance()
    if dom is None:
        return FilterResult(True, "BTC.D غير متاح — تمرير")

    # ارتفاع هيمنة قوي + شراء ألتس = خطر
    if side.lower() == "buy" and dom >= 55.0:
        return FilterResult(
            False,
            f"BTC.D مرتفعة ({dom:.1f}%) — تجنّب شراء الألتس",
        )
    if side.lower() == "sell" and dom <= 40.0:
        return FilterResult(
            False,
            f"BTC.D منخفضة ({dom:.1f}%) — تجنّب بيع الألتس عكس السيولة",
        )
    return FilterResult(True, f"BTC.D={dom:.1f}% مقبول")


# —— 14) Spoofing / Layering ——


def detect_spoofing(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    *,
    wall_mult: float = 5.0,
) -> FilterResult:
    if not _flag("spoofing_detector_enabled", True):
        return FilterResult(True, "spoofing detector معطّل")
    if not bids or not asks:
        return FilterResult(True, "دفتر فارغ — تمرير")

    bid_sizes = [s for _, s in bids[:10]]
    ask_sizes = [s for _, s in asks[:10]]
    if not bid_sizes or not ask_sizes:
        return FilterResult(True, "عمق غير كافٍ")

    avg_bid = sum(bid_sizes) / len(bid_sizes)
    avg_ask = sum(ask_sizes) / len(ask_sizes)
    max_bid = max(bid_sizes)
    max_ask = max(ask_sizes)

    if avg_bid > 0 and max_bid >= avg_bid * wall_mult and max_bid > max_ask * 2:
        return FilterResult(
            False,
            f"اشتباه Spoofing: جدار شراء {max_bid:.2f} >> متوسط {avg_bid:.2f}",
        )
    if avg_ask > 0 and max_ask >= avg_ask * wall_mult and max_ask > max_bid * 2:
        return FilterResult(
            False,
            f"اشتباه Spoofing: جدار بيع {max_ask:.2f} >> متوسط {avg_ask:.2f}",
        )
    return FilterResult(True, "لا جدران وهمية واضحة")


# —— 15) RSI + MACD divergence matrix ——


def _ema(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    out: list[float | None] = [None] * (period - 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    prev = seed
    for v in values[period:]:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def check_macd_rsi_divergence_matrix(
    closes_h1: list[float],
    closes_h4: list[float],
    *,
    direction: str,
) -> FilterResult:
    """توافق ضعف/قوة الزخم بين H1 و H4 عبر RSI+MACD المبسط."""
    if not _flag("macd_rsi_divergence_enabled", True):
        return FilterResult(True, "MACD+RSI matrix معطّل")

    if len(closes_h1) < 35 or len(closes_h4) < 35:
        return FilterResult(True, "بيانات غير كافية — تمرير")

    def macd_hist(vals: list[float]) -> float | None:
        ema12 = _ema(vals, 12)
        ema26 = _ema(vals, 26)
        if ema12[-1] is None or ema26[-1] is None:
            return None
        macd_line = [ (a - b) if a is not None and b is not None else None for a, b in zip(ema12, ema26) ]
        valid = [x for x in macd_line if x is not None]
        if len(valid) < 9:
            return None
        signal = _ema(valid, 9)
        if signal[-1] is None:
            return None
        return valid[-1] - signal[-1]

    from core.technical.indicators import rsi

    r1 = rsi(closes_h1, 14)
    r4 = rsi(closes_h4, 14)
    h1 = macd_hist(closes_h1)
    h4 = macd_hist(closes_h4)
    if r1 is None or r4 is None or h1 is None or h4 is None:
        return FilterResult(True, "مؤشرات ناقصة — تمرير")

    bullish = direction.lower() in {"buy", "bullish", "long"}
    if bullish:
        # ضعف على الإطار الأعلى يرفض شراء
        if r4 > 70 and h4 < 0 and r1 < r4:
            return FilterResult(
                False,
                f"مصفوفة انعكاس: H4 مشبع/MACD- مع RSI H1 أضعف ({r1:.1f})",
            )
    else:
        if r4 < 30 and h4 > 0 and r1 > r4:
            return FilterResult(
                False,
                f"مصفوفة انعكاس: H4 ذروة بيع/MACD+ مع RSI H1 أقوى ({r1:.1f})",
            )
    return FilterResult(True, "مصفوفة RSI+MACD متوافقة")


# —— 18) Funding guard (Futures stub) ——


def check_funding_guard(*, is_futures: bool = False) -> FilterResult:
    if not _flag("funding_guard_enabled", False):
        return FilterResult(True, "funding guard معطّل")
    if not is_futures:
        return FilterResult(True, "Spot — تخطي Funding")
    # جاهز لربطه لاحقاً بـ Binance Futures fundingTime
    now = datetime.now(timezone.utc)
    # نوافذ التسوية الشائعة: 00:00 / 08:00 / 16:00 UTC — امنع 5 دقائق قبلها
    hour = now.hour
    minute = now.minute
    settle_hours = {0, 8, 16}
    if hour in settle_hours and minute >= 55:
        return FilterResult(False, "قرب تسوية Funding — منع دخول")
    if hour in {7, 15, 23} and minute >= 55:
        return FilterResult(False, "قرب تسوية Funding — منع دخول")
    return FilterResult(True, "بعيد عن نافذة Funding")


# —— 19) Weekend flat ——


def check_weekend_flat_policy(now: datetime | None = None) -> FilterResult:
    """إن مفعّل: يمنع دخولاً جديداً قرب عطلة نهاية الأسبوع (UTC)."""
    if not _flag("weekend_flat_enabled", False):
        return FilterResult(True, "weekend flat معطّل")
    ts = now or datetime.now(timezone.utc)
    cfg = _cfg()
    weekday = int(cfg.get("weekend_flat_weekday_utc", 5))  # Friday=5
    hour = int(cfg.get("weekend_flat_hour_utc", 20))
    if ts.weekday() > weekday or (ts.weekday() == weekday and ts.hour >= hour):
        return FilterResult(False, "Weekend Flat — إيقاف دخول قبل/خلال العطلة")
    if ts.weekday() == 6:  # Sunday
        return FilterResult(False, "Weekend Flat — الأحد")
    return FilterResult(True, "خارج نافذة العطلة")


def should_force_weekend_flat(now: datetime | None = None) -> bool:
    """هل يجب إغلاق المراكز المفتوحة احترازياً؟"""
    if not _flag("weekend_flat_enabled", False):
        return False
    result = check_weekend_flat_policy(now)
    return not result.allowed
