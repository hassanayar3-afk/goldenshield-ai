"""سقوف المنظومة — 20 صفقة نخبة، حدود القادة الثلاثة."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CommanderLimits:
    smc_max: int
    flash_max: int
    momentum_max: int
    global_max: int


def load_commander_limits() -> CommanderLimits:
    def _i(key: str, default: int) -> int:
        try:
            return int(os.getenv(key, str(default)) or default)
        except (TypeError, ValueError):
            return default

    return CommanderLimits(
        smc_max=_i("SMC_MAX_CONCURRENT", 4),
        flash_max=_i("GOLD_FLASH_MAX_CONCURRENT", 12),
        momentum_max=_i("MICRO_MOMENTUM_MAX_CONCURRENT", 5),
        global_max=_i("MAX_ELITE_CONCURRENT_POSITIONS", 20),
    )


def portfolio_heat_cap_pct() -> float:
    try:
        return float(os.getenv("PORTFOLIO_HEAT_CAP_PCT", "0.07") or 0.07)
    except (TypeError, ValueError):
        return 0.07
