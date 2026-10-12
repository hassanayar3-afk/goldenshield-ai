"""بوابة فرص النخبة — لا دخول دون Score >= 85%."""

from __future__ import annotations

from dataclasses import dataclass

from platform.scoring import confidence_percent, elite_min_percent, meets_elite


@dataclass(frozen=True)
class EliteDecision:
    approved: bool
    reason: str
    confidence: float


def evaluate_elite_gate(score: int | float) -> EliteDecision:
    conf = confidence_percent(score)
    if not meets_elite(score):
        return EliteDecision(
            False,
            f"Elite Gate: {conf:.0f}% < {elite_min_percent():.0f}%",
            conf,
        )
    return EliteDecision(True, f"Elite OK {conf:.0f}%", conf)
