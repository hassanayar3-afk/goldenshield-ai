"""محاصص رأس المال المعزولة بين القادة الثلاثة."""

from __future__ import annotations

import os
from dataclasses import dataclass

from execution.models.trade import Position


@dataclass(frozen=True)
class CapitalWallDecision:
    allowed: bool
    reason: str


def _allocations() -> dict[str, float]:
    return {
        "smc_macro": float(os.getenv("CAPITAL_ALLOC_SMC_PCT", "0.35") or 0.35),
        "gold_flash": float(os.getenv("CAPITAL_ALLOC_FLASH_PCT", "0.50") or 0.50),
        "micro_momentum": float(os.getenv("CAPITAL_ALLOC_MOMENTUM_PCT", "0.15") or 0.15),
    }


def _notional(pos: Position) -> float:
    return float(pos.entry_price) * float(pos.amount)


def evaluate_capital_wall(
    commander: str,
    balance: float,
    open_positions: list[Position],
    *,
    proposed_notional: float,
) -> CapitalWallDecision:
    if balance <= 0:
        return CapitalWallDecision(False, "رصيد غير صالح")
    alloc = _allocations().get(commander, 0.33)
    cap = balance * alloc
    used = sum(
        _notional(p)
        for p in open_positions
        if getattr(p, "commander", "") == commander
    )
    if used + proposed_notional > cap * 1.05:
        return CapitalWallDecision(
            False,
            f"Capital Wall {commander}: {used + proposed_notional:.0f}$ > {cap:.0f}$",
        )
    return CapitalWallDecision(True, f"Wall OK ({commander})")
