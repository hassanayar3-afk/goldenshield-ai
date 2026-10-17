"""سقف حرارة المحفظة — 6–8% إجمالي مخاطرة مفتوحة."""

from __future__ import annotations

from dataclasses import dataclass

from execution.models.order import OrderSide
from execution.models.trade import Position
from terminal.limits import portfolio_heat_cap_pct


@dataclass(frozen=True)
class HeatDecision:
    allowed: bool
    reason: str
    heat_pct: float
    cap_pct: float


@dataclass(frozen=True)
class HeatSummary:
    open_positions: int
    heat_pct: float
    cap_pct: float
    headroom_pct: float


def _position_risk_pct(position: Position, balance: float) -> float:
    if balance <= 0:
        return 0.0
    risk_per_unit = position.risk_per_unit
    if risk_per_unit <= 0:
        return 0.0
    notional_risk = risk_per_unit * float(position.amount)
    return notional_risk / balance


def compute_heat_summary(positions: list[Position], balance: float) -> HeatSummary:
    cap = portfolio_heat_cap_pct()
    heat = sum(_position_risk_pct(p, balance) for p in positions)
    return HeatSummary(
        open_positions=len(positions),
        heat_pct=heat,
        cap_pct=cap,
        headroom_pct=max(0.0, cap - heat),
    )


def evaluate_portfolio_heat(
    positions: list[Position],
    balance: float,
    *,
    additional_risk_pct: float = 0.0,
) -> HeatDecision:
    cap = portfolio_heat_cap_pct()
    total = sum(_position_risk_pct(p, balance) for p in positions) + max(
        0.0, additional_risk_pct
    )
    if total > cap:
        return HeatDecision(
            False,
            f"Portfolio Heat {total*100:.2f}% > cap {cap*100:.1f}%",
            total,
            cap,
        )
    return HeatDecision(
        True,
        f"Heat {total*100:.2f}% / {cap*100:.1f}%",
        total,
        cap,
    )


def side_label(side: OrderSide) -> str:
    return "buy" if side == OrderSide.BUY else "sell"
