"""تقرير تيليجرام ذكي بعد الصفقة — طبقة مضافة (افتراضي: معطّل)."""

from __future__ import annotations

import logging
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)


def format_smart_trade_report(
    *,
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    stop_loss: float,
    take_profit: float,
    pnl: float,
    reason: str,
    signal_score: int = 0,
    filters: str = "",
) -> str:
    try:
        risk = abs(entry_price - stop_loss)
        move = abs(exit_price - entry_price)
        rr = (move / risk) if risk > 0 else 0.0
        sign = "+" if pnl >= 0 else ""
        side_ar = "شراء" if str(side).lower() in {"buy", "long", "orderside.buy"} else "بيع"
        filters_txt = filters or "فلاتر التنفيذ القياسية + بوابات المخاطر"
        return (
            f"📊 تقرير صفقة ذكي — {symbol}\n"
            f"الاتجاه: {side_ar}\n"
            f"الدخول: {entry_price:.5f} → الخروج: {exit_price:.5f}\n"
            f"السبب: {reason}\n"
            f"R:R المحققة ≈ {rr:.2f}\n"
            f"درجة الإشارة: {signal_score}\n"
            f"التأكيدات: {filters_txt}\n"
            f"PnL: {sign}{pnl:.2f}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("format_smart_trade_report فشل: %s", exc)
        return f"إغلاق {symbol} | PnL={pnl:.2f} | {reason}"


def maybe_send_smart_report(alerts: Any, text: str) -> bool:
    try:
        settings = get_settings()
        if not bool(getattr(settings, "smart_trade_report_enabled", False)):
            return False
        if alerts is None:
            return False
        telegram = getattr(alerts, "telegram", None)
        if telegram is None:
            return False
        return bool(telegram.send_message(text))
    except Exception as exc:  # noqa: BLE001
        logger.warning("maybe_send_smart_report فشل: %s", exc)
        return False
