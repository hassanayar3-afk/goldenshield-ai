"""صلاحيات المالك/الإدارة — البوت يتصرّف بصلاحياتك الكاملة."""

from __future__ import annotations

import os

from config.settings import get_settings


def _parse_ids(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def admin_chat_ids() -> set[str]:
    settings = get_settings()
    ids = _parse_ids(os.getenv("TELEGRAM_ADMIN_IDS"))
    if settings.telegram_chat_id:
        ids.add(str(settings.telegram_chat_id))
    watchdog = os.getenv("WATCHDOG_CHAT_ID")
    if watchdog:
        ids.add(str(watchdog))
    return ids


def is_admin(chat_id: str | int | None) -> bool:
    if chat_id is None:
        return False
    return str(chat_id) in admin_chat_ids()


def can_control_bot(chat_id: str | int | None) -> bool:
    """صلاحية كاملة: أوامر، أزرار، إضافة رموز — كأنك أنت."""
    settings = get_settings()
    if not settings.bot_admin_full_access:
        return str(chat_id) == str(settings.telegram_chat_id)
    return is_admin(chat_id)


def bot_may_auto_expand() -> bool:
    settings = get_settings()
    # Binance-only: لا توسعة MT5 أبداً ما لم يُفعَّل MT5 صراحة
    if not bool(getattr(settings, "mt5_enabled", False)):
        return False
    return settings.bot_auto_sync_mt5 and settings.bot_admin_full_access
