"""1000 محاكاة Monte Carlo قبل كل صفقة."""

from __future__ import annotations

import random
from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class MonteCarloResult:
    passed: bool
    win_rate: float
    simulations: int
    reason: str


def run_monte_carlo(
    *,
    win_probability: float = 0.45,
    simulations: int | None = None,
    min_win_rate: float | None = None,
    seed: int | None = None,
) -> MonteCarloResult:
    settings = get_settings()
    sims = simulations if simulations is not None else settings.monte_carlo_simulations
    threshold = min_win_rate if min_win_rate is not None else settings.monte_carlo_min_win_rate

    rng = random.Random(seed)
    wins = sum(1 for _ in range(sims) if rng.random() < win_probability)
    win_rate = wins / sims if sims > 0 else 0.0
    passed = win_rate >= threshold

    if passed:
        reason = f"Monte Carlo: {win_rate:.1%} ≥ {threshold:.1%}"
    else:
        reason = f"Monte Carlo مرفوض: {win_rate:.1%} < {threshold:.1%}"

    return MonteCarloResult(
        passed=passed,
        win_rate=win_rate,
        simulations=sims,
        reason=reason,
    )
