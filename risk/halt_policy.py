"""سياسة الإيقاف — Pause / Kill Switch بدون تعطيل إدارة المراكز."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class HaltDecision:
    """entries_blocked=True يمنع الدخول الجديد فقط — لا يمنع manage_positions."""

    entries_blocked: bool
    manage_positions: bool
    reason: str


def evaluate_trading_halt(
    *,
    paused: bool = False,
    kill_switch_active: bool = False,
) -> HaltDecision:
    """يفصل حظر الدخول عن إدارة المراكز المفتوحة.

    طبقة مضافة: لا تغيّر منطق Kill Switch الأصلي للرفض عند evaluate_entry.
    """
    try:
        settings = get_settings()
        manage = bool(getattr(settings, "manage_positions_during_halt", True))
        if paused:
            return HaltDecision(
                entries_blocked=True,
                manage_positions=manage,
                reason="Pause مفعّل — دخول موقوف · إدارة المراكز مستمرة",
            )
        if kill_switch_active:
            return HaltDecision(
                entries_blocked=True,
                manage_positions=manage,
                reason="Kill Switch مفعّل — دخول موقوف · إدارة المراكز مستمرة (Monitoring)",
            )
        return HaltDecision(
            entries_blocked=False,
            manage_positions=True,
            reason="تداول عادي",
        )
    except Exception as exc:  # noqa: BLE001
        # فشل آمن: امنع الدخول الجديد وأبقِ إدارة المراكز
        return HaltDecision(
            True,
            True,
            f"halt_policy خطأ — رفض دخول آمن: {exc}",
        )
