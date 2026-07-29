"""إيقاف دائم بقرار المستخدم — يمنع إعادة التشغيل التلقائي والإشارات."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

RUNTIME_DIR = BASE_DIR / "storage" / "runtime"
FLAG_PATH = RUNTIME_DIR / "user_stopped.flag"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_flag() -> dict[str, Any] | None:
    if not FLAG_PATH.exists():
        return None
    try:
        data = json.loads(FLAG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        logger.exception("فشل قراءة علامة الإيقاف")
        return {"reason": "corrupt_flag", "stopped_at": _utc_now()}


def is_user_stopped() -> bool:
    return FLAG_PATH.exists()


def stop_info() -> dict[str, Any] | None:
    return _read_flag()


def request_user_stop(reason: str, *, source: str = "user") -> None:
    """إيقاف دائم: لا إشارات ولا إعادة تشغيل تلقائي."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "reason": reason,
        "source": source,
        "stopped_at": _utc_now(),
    }
    FLAG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.warning("User stop requested: %s (%s)", reason, source)


def clear_user_stop() -> bool:
    """يُستدعى عند تشغيل 00_START.bat — المستخدم يريد العودة للعمل."""
    if not FLAG_PATH.exists():
        return False
    try:
        FLAG_PATH.unlink()
        logger.info("User stop flag cleared")
        return True
    except OSError:
        logger.exception("فشل حذف علامة الإيقاف")
        return False


def should_block_signals() -> bool:
    return is_user_stopped()
