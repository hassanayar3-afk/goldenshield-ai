"""مصفوفة الثقة GoldenShield — Opportunity Score Sizing (0–100)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from core.constants import SCORE_PERCENT_MAP, score_to_percent as legacy_score_to_percent


class ConfidenceBand(str, Enum):
    REJECTED = "rejected"
    MEDIUM = "medium"
    STRONG = "strong"
    GOLDEN = "golden"
    ELITE = "elite"


@dataclass(frozen=True)
class ConfidenceProfile:
    percent: float
    band: ConfidenceBand
    risk_pct: float
    auto_allowed: bool
    notify_allowed: bool
    legacy_percent: int


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def confidence_percent(score: int | float) -> float:
    """نسبة ثقة مستمرة: score 0–10 → 0–100 (8.5 → 85)."""
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, value * 10.0))


def elite_min_percent() -> float:
    return _env_float("ELITE_MIN_PERCENT", 85.0)


def notify_min_percent() -> float:
    return _env_float("TELEGRAM_SIGNAL_MIN_PERCENT", 70.0)


def auto_min_percent() -> float:
    return _env_float("AUTO_ENTRY_MIN_PERCENT", 90.0)


def meets_elite(score: int | float) -> bool:
    return confidence_percent(score) >= elite_min_percent()


def meets_notify(score: int | float) -> bool:
    return confidence_percent(score) >= notify_min_percent()


def meets_auto(score: int | float) -> bool:
    return confidence_percent(score) >= auto_min_percent()


def classify_band(score: int | float) -> ConfidenceBand:
    pct = confidence_percent(score)
    if pct < 70.0:
        return ConfidenceBand.REJECTED
    if pct >= 90.0:
        return ConfidenceBand.GOLDEN
    if pct >= elite_min_percent():
        return ConfidenceBand.ELITE
    if pct >= 80.0:
        return ConfidenceBand.STRONG
    return ConfidenceBand.MEDIUM


def risk_pct_for_confidence(score: int | float) -> float:
    """Opportunity Score Sizing — رفض <70%."""
    pct = confidence_percent(score)
    if pct < 70.0:
        return 0.0
    if pct >= 90.0:
        return _env_float("RISK_PCT_GOLDEN", 0.02)
    if pct >= 80.0:
        return _env_float("RISK_PCT_STRONG", 0.015)
    return _env_float("RISK_PCT_MEDIUM", 0.01)


def build_confidence_profile(score: int | float) -> ConfidenceProfile:
    pct = confidence_percent(score)
    band = classify_band(score)
    return ConfidenceProfile(
        percent=pct,
        band=band,
        risk_pct=risk_pct_for_confidence(score),
        auto_allowed=meets_auto(score),
        notify_allowed=meets_notify(score),
        legacy_percent=legacy_score_to_percent(score),
    )


def hybrid_percent(score: int | float, *, prefer_continuous: bool = True) -> int:
    """يعيد نسبة للعرض — continuous افتراضي، legacy عند prefer_continuous=False."""
    if prefer_continuous:
        return int(round(confidence_percent(score)))
    return legacy_score_to_percent(score)


def score_percent_reference_table() -> dict[str, float]:
    """جدول مرجعي للوثائق والاختبارات."""
    return {
        "reject_below": 70.0,
        "medium_70_79_risk_pct": risk_pct_for_confidence(7.5),
        "strong_80_89_risk_pct": risk_pct_for_confidence(8.5),
        "golden_90_100_risk_pct": risk_pct_for_confidence(9.5),
        "elite_min": elite_min_percent(),
        "legacy_map_8": float(SCORE_PERCENT_MAP.get(8, 75)),
        "legacy_map_9": float(SCORE_PERCENT_MAP.get(9, 90)),
    }
