"""موزّع GoldenShield Terminal — سقف 20 نخبة، Min Notional، حرارة المحفظة."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from config.project_rules import assert_entry_notional, load_project_rules
from config.settings import get_settings
from execution.models.trade import Position
from terminal.capital_walls import evaluate_capital_wall
from terminal.correlation_shield import evaluate_correlation_shield
from terminal.elite_gate import evaluate_elite_gate
from terminal.limits import CommanderLimits, load_commander_limits
from terminal.portfolio_heat import evaluate_portfolio_heat
from terminal.scoring import confidence_percent, risk_pct_for_confidence


class DispatchStage(str, Enum):
    ELITE_GATE = "elite_gate"
    GLOBAL_CAP = "global_cap"
    COMMANDER_CAP = "commander_cap"
    ONE_PER_SYMBOL = "one_per_symbol"
    CORRELATION = "correlation"
    CONFIDENCE_RISK = "confidence_risk"
    PORTFOLIO_HEAT = "portfolio_heat"
    MIN_NOTIONAL = "min_notional"
    CAPITAL_WALL = "capital_wall"
    EXECUTION_BRIDGE = "execution_bridge"
    APPROVED = "approved"


@runtime_checkable
class CommanderProposalLike(Protocol):
    commander: str
    symbol: str
    side: str
    price: float
    score: int | float
    signal: str
    reasons: tuple[str, ...]
    passed: bool


@dataclass(frozen=True)
class DispatchDecision:
    approved: bool
    reason: str
    stage: DispatchStage
    risk_pct: float = 0.0
    confidence_pct: float = 0.0


def _count_by_commander(positions: list[Position], commander: str) -> int:
    total = 0
    for position in positions:
        if getattr(position, "commander", "") == commander:
            total += 1
    return total


def _default_sl_pct() -> float:
    settings = get_settings()
    try:
        value = float(getattr(settings, "default_sl_pct", 0.03) or 0.03)
    except (TypeError, ValueError):
        value = 0.03
    return max(value, 0.001)


def _estimate_entry_amount(
    balance: float,
    price: float,
    risk_pct: float,
    sl_pct: float,
) -> float:
    if balance <= 0 or price <= 0 or risk_pct <= 0 or sl_pct <= 0:
        return 0.0
    risk_dollars = balance * risk_pct
    loss_per_unit = price * sl_pct
    if loss_per_unit <= 0:
        return 0.0
    return round(risk_dollars / loss_per_unit, 8)


def evaluate_min_notional_shield(
    *,
    price: float,
    balance: float,
    risk_pct: float,
    sl_pct: float | None = None,
) -> tuple[bool, str, float]:
    """درع الحد الأدنى — يرفض الغبار قبل الإرسال للمنصة."""
    sl = sl_pct if sl_pct is not None else _default_sl_pct()
    amount = _estimate_entry_amount(balance, price, risk_pct, sl)
    if amount <= 0:
        return False, "Min Notional: حجم تقديري صفر", amount
    dust = assert_entry_notional(amount, price, force_open=False)
    if dust:
        rules = load_project_rules()
        exchange_min = float(getattr(rules, "min_exchange_notional", 5.0) or 5.0)
        notional = amount * price
        if notional < exchange_min:
            return (
                False,
                f"Min Notional: {notional:.2f}$ < حد المنصة {exchange_min:.2f}$",
                amount,
            )
        return False, f"Min Notional: {dust}", amount
    return True, "Min Notional OK", amount


def evaluate_dispatch(
    proposal: CommanderProposalLike,
    *,
    open_positions: list[Position],
    balance: float,
    limits: CommanderLimits | None = None,
) -> DispatchDecision:
    lim = limits or load_commander_limits()
    confidence = confidence_percent(proposal.score)

    elite = evaluate_elite_gate(proposal.score)
    if not elite.approved:
        return DispatchDecision(
            False,
            elite.reason,
            DispatchStage.ELITE_GATE,
            confidence_pct=confidence,
        )

    if len(open_positions) >= lim.global_max:
        return DispatchDecision(
            False,
            f"Global cap {lim.global_max} صفقات مفتوحة",
            DispatchStage.GLOBAL_CAP,
            confidence_pct=confidence,
        )

    commander = str(proposal.commander or "")
    cap_by_commander: dict[str, int] = {
        "smc_macro": lim.smc_max,
        "gold_flash": lim.flash_max,
        "micro_momentum": lim.momentum_max,
    }
    commander_cap = cap_by_commander.get(commander, lim.global_max)
    if _count_by_commander(open_positions, commander) >= commander_cap:
        return DispatchDecision(
            False,
            f"Cap {commander} = {commander_cap} صفقة",
            DispatchStage.COMMANDER_CAP,
            confidence_pct=confidence,
        )

    for position in open_positions:
        if position.symbol == proposal.symbol:
            return DispatchDecision(
                False,
                f"صفقة واحدة لكل زوج ({proposal.symbol})",
                DispatchStage.ONE_PER_SYMBOL,
                confidence_pct=confidence,
            )

    correlation = evaluate_correlation_shield(
        proposal.symbol,
        proposal.side,
        open_positions,
    )
    if not correlation.allowed:
        return DispatchDecision(
            False,
            correlation.reason,
            DispatchStage.CORRELATION,
            confidence_pct=confidence,
        )

    risk_pct = risk_pct_for_confidence(proposal.score)
    if risk_pct <= 0:
        return DispatchDecision(
            False,
            "Score < 70% — رفض قاطع",
            DispatchStage.CONFIDENCE_RISK,
            confidence_pct=confidence,
        )

    heat = evaluate_portfolio_heat(
        open_positions,
        balance,
        additional_risk_pct=risk_pct,
    )
    if not heat.allowed:
        return DispatchDecision(
            False,
            heat.reason,
            DispatchStage.PORTFOLIO_HEAT,
            risk_pct=risk_pct,
            confidence_pct=confidence,
        )

    min_ok, min_reason, _amount = evaluate_min_notional_shield(
        price=float(proposal.price),
        balance=balance,
        risk_pct=risk_pct,
    )
    if not min_ok:
        return DispatchDecision(
            False,
            min_reason,
            DispatchStage.MIN_NOTIONAL,
            risk_pct=risk_pct,
            confidence_pct=confidence,
        )

    proposed_notional = balance * risk_pct
    wall = evaluate_capital_wall(
        commander,
        balance,
        open_positions,
        proposed_notional=proposed_notional,
    )
    if not wall.allowed:
        return DispatchDecision(
            False,
            wall.reason,
            DispatchStage.CAPITAL_WALL,
            risk_pct=risk_pct,
            confidence_pct=confidence,
        )

    return DispatchDecision(
        True,
        f"Dispatch OK [{commander}] conf={confidence:.0f}% risk={risk_pct*100:.2f}%",
        DispatchStage.APPROVED,
        risk_pct=risk_pct,
        confidence_pct=confidence,
    )


def evaluate_dispatch_batch(
    proposals: list[CommanderProposalLike],
    *,
    open_positions: list[Position],
    balance: float,
    limits: CommanderLimits | None = None,
) -> list[tuple[CommanderProposalLike, DispatchDecision]]:
    """يفحص قائمة مقترحات مع تحديث افتراضي للمراكز بعد كل موافقة."""
    lim = limits or load_commander_limits()
    working_positions = list(open_positions)
    working_balance = float(balance)
    ordered = sorted(
        proposals,
        key=lambda p: confidence_percent(p.score),
        reverse=True,
    )
    results: list[tuple[CommanderProposalLike, DispatchDecision]] = []
    for proposal in ordered:
        decision = evaluate_dispatch(
            proposal,
            open_positions=working_positions,
            balance=working_balance,
            limits=lim,
        )
        results.append((proposal, decision))
        if decision.approved:
            working_positions = list(working_positions)
    return results


def dispatch_strict_mode_enabled() -> bool:
    raw = (os.getenv("TERMINAL_DISPATCH_STRICT", "true") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}
