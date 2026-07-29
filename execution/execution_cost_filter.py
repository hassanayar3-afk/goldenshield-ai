"""فلتر تكلفة التنفيذ — سبريد/عمولة مقابل الربح المتوقع (Standard/Bonus)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionCostResult:
    allowed: bool
    cost_pct_of_target: float
    reason: str


def check_execution_cost(
    *,
    entry_price: float,
    take_profit: float,
    spread_pct: float | None,
    max_cost_to_profit_pct: float,
) -> ExecutionCostResult:
    if entry_price <= 0 or take_profit <= 0:
        return ExecutionCostResult(True, 0.0, "بيانات غير كافية — تمرير افتراضي")

    expected_move = abs(take_profit - entry_price)
    if expected_move <= 0:
        return ExecutionCostResult(False, 100.0, "الربح المتوقع صفر")

    spread = spread_pct if spread_pct is not None else 0.0
    cost = entry_price * (spread / 100.0)
    ratio = (cost / expected_move) * 100.0
    if ratio <= max_cost_to_profit_pct:
        return ExecutionCostResult(
            True,
            ratio,
            f"تكلفة التنفيذ {ratio:.1f}% من الهدف — مقبولة",
        )
    return ExecutionCostResult(
        False,
        ratio,
        f"تكلفة التنفيذ {ratio:.1f}% > {max_cost_to_profit_pct:.1f}% من الربح المتوقع",
    )
