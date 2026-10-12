"""موزّع مركزي — سقف 20، نخبة، صفقة واحدة/زوج، حدود القادة."""

from __future__ import annotations

from dataclasses import dataclass

from terminal.capital_walls import evaluate_capital_wall
from terminal.correlation_shield import evaluate_correlation_shield
from terminal.elite_gate import evaluate_elite_gate
from terminal.limits import CommanderLimits, load_commander_limits
from terminal.portfolio_heat import evaluate_portfolio_heat
from terminal.scoring import risk_pct_for_confidence


@dataclass(frozen=True)
class DispatchDecision:
    approved: bool
    reason: str
    risk_pct: float = 0.0


def _count_by_commander(positions, commander: str) -> int:
    return sum(1 for p in positions if getattr(p, "commander", "") == commander)


def evaluate_dispatch(
    proposal,
    *,
    open_positions: list,
    balance: float,
    limits: CommanderLimits | None = None,
) -> DispatchDecision:
    lim = limits or load_commander_limits()
    elite = evaluate_elite_gate(proposal.score)
    if not elite.approved:
        return DispatchDecision(False, elite.reason)

    if len(open_positions) >= lim.global_max:
        return DispatchDecision(False, f"Global cap {lim.global_max} صفقات")

    cmd = proposal.commander
    cap_map = {
        "smc_macro": lim.smc_max,
        "gold_flash": lim.flash_max,
        "micro_momentum": lim.momentum_max,
    }
    cmd_cap = cap_map.get(cmd, lim.global_max)
    if _count_by_commander(open_positions, cmd) >= cmd_cap:
        return DispatchDecision(False, f"Cap {cmd} = {cmd_cap}")

    if any(p.symbol == proposal.symbol for p in open_positions):
        return DispatchDecision(False, f"صفقة واحدة لكل زوج ({proposal.symbol})")

    corr = evaluate_correlation_shield(
        proposal.symbol, proposal.side, open_positions
    )
    if not corr.allowed:
        return DispatchDecision(False, corr.reason)

    risk_pct = risk_pct_for_confidence(proposal.score)
    if risk_pct <= 0:
        return DispatchDecision(False, "Score < 70% — رفض")

    heat = evaluate_portfolio_heat(open_positions, balance, additional_risk_pct=risk_pct)
    if not heat.allowed:
        return DispatchDecision(False, heat.reason)

    notional = balance * risk_pct
    wall = evaluate_capital_wall(cmd, balance, open_positions, proposed_notional=notional)
    if not wall.allowed:
        return DispatchDecision(False, wall.reason)

    return DispatchDecision(True, f"Dispatch OK [{cmd}]", risk_pct=risk_pct)
