"""تنفيذ gold_flash — Maker-only، TP1 vs عمولات، Min Notional."""

from __future__ import annotations

from dataclasses import dataclass

from config.project_rules import assert_entry_notional


@dataclass(frozen=True)
class FlashExecutionPlan:
    approved: bool
    reason: str
    use_maker: bool = True
    tp1_covers_fees: bool = False


def min_notional_usdt() -> float:
    import os

    try:
        return max(
            5.0,
            float(os.getenv("PROJECT_MIN_EXCHANGE_NOTIONAL", "5") or 5),
        )
    except (TypeError, ValueError):
        return 5.0


def evaluate_fee_aware_tp1(
    *,
    entry: float,
    tp1: float,
    amount: float,
    fee_rate: float = 0.001,
    fee_multiplier: float = 3.0,
) -> FlashExecutionPlan:
    if entry <= 0 or tp1 <= 0 or amount <= 0:
        return FlashExecutionPlan(False, "خطة غير صالحة")
    if assert_entry_notional(amount, entry):
        return FlashExecutionPlan(
            False,
            f"Min Notional — قيمة {amount * entry:.2f}$ دون الحد",
        )
    notional = amount * entry
    est_fees = notional * fee_rate * 2
    tp1_profit = abs(tp1 - entry) * amount
    covers = tp1_profit >= est_fees * fee_multiplier
    if not covers:
        return FlashExecutionPlan(
            False,
            f"TP1 {tp1_profit:.2f}$ لا يغطي 3× العمولة ({est_fees*fee_multiplier:.2f}$)",
        )
    return FlashExecutionPlan(True, "Maker + TP1 fee-safe", use_maker=True, tp1_covers_fees=True)
