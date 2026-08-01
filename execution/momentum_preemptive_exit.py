"""خروج استباقي عند انهيار زخم قصير (اختياري — default off)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from execution.models.order import OrderSide
from execution.models.trade import Position
from intelligence.cognitive_config import momentum_preemptive_exit_enabled

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MomentumExitAction:
    should_exit: bool
    reason: str = ""


def evaluate_momentum_preemptive_exit(
    position: Position,
    current_price: float,
    *,
    recent_closes: list[float] | None = None,
) -> MomentumExitAction:
    try:
        if not momentum_preemptive_exit_enabled():
            return MomentumExitAction(False)
        closes = list(recent_closes or [])
        if len(closes) < 3:
            return MomentumExitAction(False)
        # انهيار زخم: آخر إغلاق أسوأ من متوسط الثلاثة السابقة ضد الصفقة
        last = float(closes[-1])
        avg_prev = sum(float(x) for x in closes[-4:-1]) / 3.0
        if position.side == OrderSide.BUY:
            if last < avg_prev * 0.997 and current_price < position.entry_price:
                return MomentumExitAction(
                    True,
                    "خروج استباقي: انهيار زخم قصير ضد صفقة الشراء",
                )
        else:
            if last > avg_prev * 1.003 and current_price > position.entry_price:
                return MomentumExitAction(
                    True,
                    "خروج استباقي: انهيار زخم قصير ضد صفقة البيع",
                )
        return MomentumExitAction(False)
    except Exception as exc:  # noqa: BLE001
        logger.debug("evaluate_momentum_preemptive_exit: %s", exc)
        return MomentumExitAction(False)
