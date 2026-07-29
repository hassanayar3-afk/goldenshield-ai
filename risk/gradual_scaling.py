"""زيادة العقود بعد نمو 20%."""

from __future__ import annotations

from config.settings import get_settings


def scaling_multiplier(initial_balance: float, current_balance: float) -> float:
    if initial_balance <= 0:
        return 1.0

    settings = get_settings()
    growth_pct = ((current_balance - initial_balance) / initial_balance) * 100

    if growth_pct < settings.gradual_growth_threshold_pct:
        return 1.0

    # +10% حجم لكل 20% نمو — بحد أقصى 50%
    steps = int(growth_pct // settings.gradual_growth_threshold_pct)
    return min(1.0 + (steps * 0.1), 1.5)
