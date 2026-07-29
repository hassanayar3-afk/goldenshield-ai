from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from data.models.orderbook import OrderBook, OrderBookLevel
from data.orderbook_fetcher import OrderBookFetcher


@dataclass(frozen=True)
class WhaleZone:
    side: str
    price: float
    amount: float
    strength_ratio: float


@dataclass(frozen=True)
class WhaleTrackerResult:
    zones: tuple[WhaleZone, ...]
    has_whale_support: bool
    has_whale_resistance: bool
    reason: str


def _average_amount(levels: tuple[OrderBookLevel, ...]) -> float:
    if not levels:
        return 0.0
    return sum(level.amount for level in levels) / len(levels)


def track_whales(symbol: str, *, orderbook: OrderBook | None = None) -> WhaleTrackerResult:
    from config.runtime_profile import uses_binance_orderbook

    # فوركس/أسهم ليست على Binance — لا تستدعِ orderbook وإلا يفشل التحليل أو يتأخر كثيراً
    if orderbook is None and not uses_binance_orderbook(symbol):
        return WhaleTrackerResult(
            zones=(),
            has_whale_support=True,
            has_whale_resistance=True,
            reason="سيولة orderbook غير مطبّقة (فوركس/أسهم) — الاعتماد على التحليل الفني",
        )

    settings = get_settings()
    book = orderbook or OrderBookFetcher().fetch(symbol, depth=20, use_cache=True)

    bid_avg = _average_amount(book.bids)
    ask_avg = _average_amount(book.asks)
    zones: list[WhaleZone] = []

    for level in book.bids:
        if bid_avg > 0 and level.amount >= bid_avg * settings.whale_wall_multiplier:
            zones.append(
                WhaleZone(
                    side="bid",
                    price=level.price,
                    amount=level.amount,
                    strength_ratio=level.amount / bid_avg,
                )
            )

    for level in book.asks:
        if ask_avg > 0 and level.amount >= ask_avg * settings.whale_wall_multiplier:
            zones.append(
                WhaleZone(
                    side="ask",
                    price=level.price,
                    amount=level.amount,
                    strength_ratio=level.amount / ask_avg,
                )
            )

    has_support = any(zone.side == "bid" for zone in zones)
    has_resistance = any(zone.side == "ask" for zone in zones)
    return WhaleTrackerResult(
        zones=tuple(zones),
        has_whale_support=has_support,
        has_whale_resistance=has_resistance,
        reason=f"رصد {len(zones)} منطقة سيولة كبيرة",
    )
