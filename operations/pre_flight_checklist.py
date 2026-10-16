"""فحص ما قبل التشغيل — يمنع البدء عند الفشل الحرج فقط."""

from __future__ import annotations

from dataclasses import dataclass, field

from config.settings import get_settings
from data.connection_monitor import ConnectionMonitor
from operations.api_watchdog import ApiWatchdog

_SOFT_CHECK_NAMES = frozenset({"discord_optional", "warning"})


@dataclass(frozen=True)
class PreFlightCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class PreFlightResult:
    ok: bool
    checks: list[PreFlightCheck] = field(default_factory=list)


def run_pre_flight(
    *,
    connection_monitor: ConnectionMonitor | None = None,
    skip_binance_ping: bool = False,
) -> PreFlightResult:
    settings = get_settings()
    checks: list[PreFlightCheck] = []

    monitor = None if skip_binance_ping else connection_monitor
    watchdog = ApiWatchdog().run(monitor)

    for key, passed in watchdog.checks.items():
        soft = key in _SOFT_CHECK_NAMES
        detail = "OK" if passed else ("تحذير — متابعة" if soft else "فشل")
        checks.append(
            PreFlightCheck(
                name=key,
                passed=True if soft else passed,
                detail=detail if passed or soft else "فشل",
            )
        )
        if soft and not passed:
            checks[-1] = PreFlightCheck(
                name=key,
                passed=True,
                detail=f"تحذير: {watchdog.failures[-1] if watchdog.failures else 'تحقق لاحق'}",
            )

    for failure in watchdog.failures:
        warn = failure.startswith("تحذير")
        checks.append(
            PreFlightCheck(
                name="warning" if warn else "failure",
                passed=warn,
                detail=failure,
            )
        )

    if settings.min_account_balance <= 0:
        checks.append(
            PreFlightCheck(
                name="min_account_balance",
                passed=False,
                detail="الحد الأدنى للرصيد غير صالح",
            )
        )

    discord_ready = bool(
        (getattr(settings, "discord_bot_token", None) or getattr(settings, "discord_webhook_url", None))
    )
    checks.append(
        PreFlightCheck(
            name="discord_optional",
            passed=True,
            detail="Discord configured" if discord_ready else "اختياري — Discord bot/webhook غير مُعد",
        )
    )

    ok = all(c.passed for c in checks if c.name not in _SOFT_CHECK_NAMES)
    return PreFlightResult(ok=ok, checks=checks)
