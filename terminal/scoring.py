"""مصفوفة الثقة — نسبة مستمرة 0–100 من درجة 0–10 (85+ نخبة)."""

from __future__ import annotations

import os


def confidence_percent(score: int | float) -> float:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, s * 10.0))


def elite_min_percent() -> float:
    try:
        return float(os.getenv("ELITE_MIN_PERCENT", "85") or 85)
    except (TypeError, ValueError):
        return 85.0


def meets_elite(score: int | float) -> bool:
    return confidence_percent(score) >= elite_min_percent()


def risk_pct_for_confidence(score: int | float) -> float:
    """Opportunity Score Sizing — رفض <70%."""
    pct = confidence_percent(score)
    if pct < 70.0:
        return 0.0
    if pct >= 90.0:
        return 0.02
    if pct >= 80.0:
        return 0.015
    return 0.01
