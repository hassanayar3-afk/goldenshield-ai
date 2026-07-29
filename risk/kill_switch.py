"""Kill Switch — إيقاف عند −3% يومياً."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class KillSwitchResult:
    triggered: bool
    reason: str
    daily_pnl_pct: float


def check_kill_switch(daily_pnl_pct: float) -> KillSwitchResult:
    settings = get_settings()
    threshold = settings.kill_switch_daily_pct

    if daily_pnl_pct <= threshold:
        return KillSwitchResult(
            triggered=True,
            reason=f"Kill Switch: خسارة يومية {daily_pnl_pct:.2f}% ≤ {threshold}%",
            daily_pnl_pct=daily_pnl_pct,
        )

    return KillSwitchResult(
        triggered=False,
        reason="Kill Switch غير مفعّل",
        daily_pnl_pct=daily_pnl_pct,
    )
