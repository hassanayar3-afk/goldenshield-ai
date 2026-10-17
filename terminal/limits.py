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

    def as_dict(self) -> dict[str, int]:
        return {
            "smc_macro": self.smc_max,
            "gold_flash": self.flash_max,
            "micro_momentum": self.momentum_max,
            "global_max": self.global_max,
        }


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def load_commander_limits() -> CommanderLimits:
    return CommanderLimits(
        smc_max=_env_int("SMC_MAX_CONCURRENT", 4),
        flash_max=_env_int("GOLD_FLASH_MAX_CONCURRENT", 12),
        momentum_max=_env_int("MICRO_MOMENTUM_MAX_CONCURRENT", 5),
        global_max=_env_int("MAX_ELITE_CONCURRENT_POSITIONS", 20),
    )


def portfolio_heat_cap_pct() -> float:
    try:
        value = float(os.getenv("PORTFOLIO_HEAT_CAP_PCT", "0.07") or 0.07)
    except (TypeError, ValueError):
        value = 0.07
    return max(0.01, min(0.20, value))


def validate_limits(limits: CommanderLimits | None = None) -> CommanderLimits:
    lim = limits or load_commander_limits()
    per_commander = lim.smc_max + lim.flash_max + lim.momentum_max
    if per_commander < lim.global_max:
        return lim
    return CommanderLimits(
        smc_max=min(lim.smc_max, lim.global_max),
        flash_max=min(lim.flash_max, lim.global_max),
        momentum_max=min(lim.momentum_max, lim.global_max),
        global_max=lim.global_max,
    )
