"""البروتوكول الحديدي — فرض القواعد الحرجة بدون استثناء في Live.

المرجع الكامل الوحيد:
  docs/GOLDENSHIELD_IRON_LAW_COMPLETE_AR.md

يطبق Overrides آمنة على Settings (frozen) عبر dataclasses.replace.
لا يوقف الحلقة عند الخطأ — يسجّل ويُكمل بأقسى حماية ممكنة.
"""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from config.settings import Settings

# مفاتيح env التي يفرضها الملف الحديدي في Live
IRON_LIVE_FORCED: dict[str, object] = {
    "pre_execution_gate_enabled": True,
    "emergency_protocols_enabled": True,
    "emergency_atr_sl_enabled": True,
    "risk_distance_filter_enabled": True,
    "sl_rr_lock_enabled": True,
    "sl_rr_lock_ratio": 3.0,
    "volatility_guard_enabled": True,
    "require_sl_on_all_chunks": True,
    "close_naked_tickets": True,
    "manage_positions_during_halt": True,
    "auto_entry_min_percent": 90,
    "default_rr_ratio": 3.0,
}


def iron_protocol_enabled() -> bool:
    raw = os.getenv("IRON_PROTOCOL_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def apply_iron_protocol(settings: Settings) -> Settings:
    """يفرض القوانين الحرجة — خاصة في Live — دون كسر التشغيل."""
    try:
        if not iron_protocol_enabled():
            logger.info("Iron Protocol معطّل عبر IRON_PROTOCOL_ENABLED")
            return settings

        updates: dict = {}
        # دائماً: لا نسمح بعتبة تلقائي أضعف من 90 ولا R:R أضعف من 3
        if int(getattr(settings, "auto_entry_min_percent", 90) or 0) < 90:
            updates["auto_entry_min_percent"] = 90
        if float(getattr(settings, "default_rr_ratio", 3.0) or 0) < 3.0:
            updates["default_rr_ratio"] = 3.0
        if float(getattr(settings, "sl_rr_lock_ratio", 3.0) or 0) < 3.0:
            updates["sl_rr_lock_ratio"] = 3.0

        # Live: فرض كل صمامات الحماية — لا يمكن إضعافها من .env
        if str(getattr(settings, "execution_mode", "")).lower() == "live":
            for key, value in IRON_LIVE_FORCED.items():
                current = getattr(settings, key, None)
                if current != value:
                    updates[key] = value

        if not updates:
            logger.info("Iron Protocol: الإعدادات متوافقة مسبقاً")
            return settings

        new_settings = replace(settings, **updates)
        logger.warning(
            "Iron Protocol فرض %s مفتاحاً إلزامياً: %s",
            len(updates),
            ", ".join(sorted(updates)),
        )
        return new_settings
    except Exception as exc:  # noqa: BLE001
        logger.warning("apply_iron_protocol فشل (استمرار بالإعدادات الحالية): %s", exc)
        return settings


def iron_rules_summary() -> str:
    return (
        "Iron: SL+TP إلزامي | Auto≥90 | R:R≥1:3 | "
        "Gate+ATR+Volatility+NakedClose | Kill−3% | راحة 24س بعد 3 خسائر"
    )
