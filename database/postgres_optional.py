"""PostgreSQL اختياري للسجلات المؤسسية — SQLite يبقى افتراضي التشغيل."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def postgres_enabled() -> bool:
    return bool((os.getenv("POSTGRES_DSN") or "").strip())


def log_postgres_status() -> None:
    if postgres_enabled():
        logger.info("PostgreSQL DSN configured — mirror/archive mode")
    else:
        logger.debug("PostgreSQL غير مفعّل — SQLite SSOT")
