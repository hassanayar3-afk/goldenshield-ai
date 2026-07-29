from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from core.liquidity.whale_tracker import WhaleTrackerResult, track_whales
from data.models.orderbook import OrderBook


@dataclass(frozen=True)
class InstitutionalZone:
    side: str
    price: float
    amount: float


@dataclass(frozen=True)
class InstitutionalZonesResult:
    zones: tuple[InstitutionalZone, ...]
    has_bid_cluster: bool
    has_ask_cluster: bool
    reason: str


def detect_institutional_zones(
    symbol: str,
    *,
    whale_result: WhaleTrackerResult | None = None,
    orderbook: OrderBook | None = None,
) -> InstitutionalZonesResult:
    settings = get_settings()
    whales = whale_result or track_whales(symbol, orderbook=orderbook)

    institutional = [
        InstitutionalZone(side=zone.side, price=zone.price, amount=zone.amount)
        for zone in whales.zones
        if zone.strength_ratio >= settings.whale_wall_multiplier
    ]

    bid_clusters = [zone for zone in institutional if zone.side == "bid"]
    ask_clusters = [zone for zone in institutional if zone.side == "ask"]
    has_bid_cluster = len(bid_clusters) >= settings.institutional_min_levels
    has_ask_cluster = len(ask_clusters) >= settings.institutional_min_levels

    return InstitutionalZonesResult(
        zones=tuple(institutional),
        has_bid_cluster=has_bid_cluster,
        has_ask_cluster=has_ask_cluster,
        reason=(
            f"{len(institutional)} مراكز مؤسساتية"
            if institutional
            else "لا مراكز مؤسساتية واضحة"
        ),
    )
