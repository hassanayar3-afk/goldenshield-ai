"""فحص ما قبل التشغيل — يمنع البدء عند الفشل الحرج فقط."""

from __future__ import annotations

from dataclasses import dataclass, field

from config.settings import get_settings
from data.connection_monitor import ConnectionMonitor
from operations.api_watchdog import ApiWatchdog
from operations.telegram_utils import validate_chat_id

# فحوصات غير قاتلة — البوت يكمل الجلب/الإشارات حتى لو فشلت
_SOFT_CHECK_NAMES = frozenset({"mt5_ping", "telegram_optional", "warning"})


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
            # أظهر التحذير بوضوح مع الإبقاء على passed=True للناتج الكلي
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

    telegram_ready = bool(settings.telegram_token and settings.telegram_chat_id)
    chat_ok, chat_detail = validate_chat_id(
        settings.telegram_token,
        settings.telegram_chat_id,
    )
    checks.append(
        PreFlightCheck(
            name="telegram_optional",
            passed=True,
            detail="مُهيّأ" if telegram_ready and chat_ok else "اختياري — غير مُعدّ (تنبيهات محلية فقط)",
        )
    )
    if settings.telegram_chat_id:
        checks.append(
            PreFlightCheck(
                name="telegram_chat_id",
                passed=chat_ok,
                detail=chat_detail,
            )
        )

    ok = all(c.passed for c in checks if c.name not in _SOFT_CHECK_NAMES)
    return PreFlightResult(ok=ok, checks=checks)
