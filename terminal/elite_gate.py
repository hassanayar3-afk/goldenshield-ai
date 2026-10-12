"""بوابة فرص النخبة — Elite Filter Gate (≥85%) + تمييز Auto/Notify."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from terminal.scoring import (
    ConfidenceBand,
    build_confidence_profile,
    confidence_percent,
    elite_min_percent,
    meets_elite,
    meets_auto,
    meets_notify,
    risk_pct_for_confidence,
)


class EliteTier(str, Enum):
    BELOW_ELITE = "below_elite"
    ELITE_BORDER = "elite_border"
    STRONG_ELITE = "strong_elite"
    GOLDEN = "golden"


@dataclass(frozen=True)
class EliteDecision:
    approved: bool
    reason: str
    confidence: float
    tier: EliteTier
    risk_pct: float
    auto_allowed: bool
    notify_allowed: bool
    band: ConfidenceBand


def _classify_tier(score: int | float) -> EliteTier:
    pct = confidence_percent(score)
    if pct < elite_min_percent():
        return EliteTier.BELOW_ELITE
    if pct >= 90.0:
        return EliteTier.GOLDEN
    if pct >= 88.0:
        return EliteTier.STRONG_ELITE
    return EliteTier.ELITE_BORDER


def strict_elite_only() -> bool:
    raw = (os.getenv("ELITE_GATE_STRICT", "true") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def evaluate_elite_gate(score: int | float) -> EliteDecision:
    profile = build_confidence_profile(score)
    tier = _classify_tier(score)
    conf = profile.percent

    if not meets_elite(score):
        return EliteDecision(
            approved=False,
            reason=f"Elite Gate: {conf:.0f}% < {elite_min_percent():.0f}%",
            confidence=conf,
            tier=tier,
            risk_pct=0.0,
            auto_allowed=False,
            notify_allowed=profile.notify_allowed,
            band=profile.band,
        )

    risk_pct = risk_pct_for_confidence(score)
    if strict_elite_only() and risk_pct <= 0.0:
        return EliteDecision(
            approved=False,
            reason=f"Elite Gate: band {profile.band.value} — risk sizing rejected",
            confidence=conf,
            tier=tier,
            risk_pct=0.0,
            auto_allowed=False,
            notify_allowed=profile.notify_allowed,
            band=profile.band,
        )

    return EliteDecision(
        approved=True,
        reason=f"Elite OK {conf:.0f}% tier={tier.value}",
        confidence=conf,
        tier=tier,
        risk_pct=risk_pct,
        auto_allowed=meets_auto(score),
        notify_allowed=meets_notify(score),
        band=profile.band,
    )


def evaluate_elite_for_entry(
    score: int | float,
    *,
    for_auto_open: bool = True,
) -> EliteDecision:
    decision = evaluate_elite_gate(score)
    if not decision.approved:
        return decision
    if for_auto_open and not decision.auto_allowed:
        return EliteDecision(
            approved=False,
            reason=(
                f"Elite OK لكن Auto يتطلب ≥90% — الحالي {decision.confidence:.0f}%"
            ),
            confidence=decision.confidence,
            tier=decision.tier,
            risk_pct=decision.risk_pct,
            auto_allowed=False,
            notify_allowed=decision.notify_allowed,
            band=decision.band,
        )
    if not for_auto_open and not decision.notify_allowed:
        return EliteDecision(
            approved=False,
            reason=f"Notify يتطلب ≥70% — الحالي {decision.confidence:.0f}%",
            confidence=decision.confidence,
            tier=decision.tier,
            risk_pct=0.0,
            auto_allowed=decision.auto_allowed,
            notify_allowed=False,
            band=decision.band,
        )
    return decision
