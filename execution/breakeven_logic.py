"""Breakeven عند 1:1 + Partial Exit."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from execution.models.order import OrderSide
from execution.models.trade import Position


@dataclass(frozen=True)
class BreakevenAction:
    move_sl_to_breakeven: bool = False
    partial_exit_amount: float = 0.0
    new_stop_loss: float | None = None
    mark_partial_exit: bool = False
    reason: str = ""


def evaluate_breakeven(position: Position, current_price: float) -> BreakevenAction:
    settings = get_settings()
    if not settings.breakeven_enabled:
        return BreakevenAction()

    if position.risk_per_unit <= 0:
        return BreakevenAction()

    reached_one_to_one = False
    if position.side == OrderSide.BUY:
        reached_one_to_one = current_price >= position.one_to_one_price
    else:
        reached_one_to_one = current_price <= position.one_to_one_price

    if not reached_one_to_one:
        return BreakevenAction()

    move_sl = not position.breakeven_applied
    partial_amount = 0.0
    mark_partial = False
    if not position.partial_exit_done and position.amount > 0:
        partial_amount = round(position.amount * settings.partial_exit_pct, 8)
        mark_partial = True

    return BreakevenAction(
        move_sl_to_breakeven=move_sl,
        partial_exit_amount=partial_amount,
        new_stop_loss=position.entry_price if move_sl else None,
        mark_partial_exit=mark_partial,
        reason="هدف 1:1 — Breakeven + Partial Exit",
    )
