"""بوابة اختلال دفتر الأوامر (Level-2 خفيف)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from intelligence.cognitive_config import (
    orderbook_imbalance_enabled,
    orderbook_imbalance_min,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderBookGateResult:
    approved: bool
    imbalance: float
    reason: str


def evaluate_orderbook_imbalance(
    symbol: str,
    *,
    side: str,
) -> OrderBookGateResult:
    """يرفض الدخول إن كان العمق ضد اتجاه الصفقة بقوة واضحة."""
    try:
        if not orderbook_imbalance_enabled():
            return OrderBookGateResult(True, 0.0, "orderbook gate off")

        from data.orderbook_fetcher import OrderBookFetcher

        book = OrderBookFetcher().fetch(symbol, depth=20)
        bid_v = float(book.bid_volume)
        ask_v = float(book.ask_volume)
        total = bid_v + ask_v
        if total <= 0:
            return OrderBookGateResult(True, 0.0, "empty book — pass")

        # +1 = سيولة شراء مهيمنة، -1 = بيع مهيمن
        imbalance = (bid_v - ask_v) / total
        need = orderbook_imbalance_min()
        side_l = side.lower()

        # جدار وهمي بسيط: طرف واحد > 85% من العمق
        spoofish = abs(imbalance) >= 0.85
        if spoofish:
            return OrderBookGateResult(
                False,
                imbalance,
                f"فخ سيولة محتمل (imbalance={imbalance:.2f})",
            )

        if side_l == "buy" and imbalance < -need:
            return OrderBookGateResult(
                False,
                imbalance,
                f"عمق البيع ضد الشراء (imbalance={imbalance:.2f})",
            )
        if side_l == "sell" and imbalance > need:
            return OrderBookGateResult(
                False,
                imbalance,
                f"عمق الشراء ضد البيع (imbalance={imbalance:.2f})",
            )
        return OrderBookGateResult(True, imbalance, f"orderbook ok ({imbalance:.2f})")
    except Exception as exc:  # noqa: BLE001
        logger.warning("evaluate_orderbook_imbalance: %s", exc)
        return OrderBookGateResult(True, 0.0, f"orderbook gate error pass: {exc}")
