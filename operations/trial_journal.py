"""سجل مرحلة التجربة — تتبع الصفقات للتقييم دون التأثير على التنفيذ."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR, get_settings

logger = logging.getLogger(__name__)

JOURNAL_PATH = BASE_DIR / "storage" / "logs" / "trial_journal.jsonl"


def _activity_journal_always() -> bool:
    """طبقة مضافة: تسجيل الصفقات للأرشيف الشهري حتى خارج trial_mode."""
    raw = os.getenv("ACTIVITY_JOURNAL_ALWAYS", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _journal_enabled() -> bool:
    settings = get_settings()
    if not settings.trial_journal_enabled:
        return False
    return bool(settings.trial_mode or _activity_journal_always())


def log_trial_event(event: str, **fields: Any) -> None:
    """يسجّل حدث تجربة في JSONL — لا يُرسل تيليجرام ولا يغيّر التنفيذ."""
    if not _journal_enabled():
        return

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    try:
        JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("فشل كتابة سجل التجربة")

    # نسخة في أرشيف الشهر للمراجعة (إيجابيات/سلبيات)
    try:
        from operations.report_archive import log_bot_activity

        log_bot_activity(event, **fields)
    except Exception:
        pass


def log_trade_open(
    *,
    symbol: str,
    position_id: str,
    entry_price: float,
    amount: float,
    stop_loss: float,
    take_profit: float,
    score: int | None = None,
    mode: str = "paper",
) -> None:
    log_trial_event(
        "trade_open",
        symbol=symbol,
        position_id=position_id,
        entry_price=entry_price,
        amount=amount,
        stop_loss=stop_loss,
        take_profit=take_profit,
        score=score,
        mode=mode,
    )


def log_trade_close(
    *,
    symbol: str,
    position_id: str,
    exit_price: float,
    pnl: float,
    reason: str,
) -> None:
    log_trial_event(
        "trade_close",
        symbol=symbol,
        position_id=position_id,
        exit_price=exit_price,
        pnl=pnl,
        reason=reason,
    )
