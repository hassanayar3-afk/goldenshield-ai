"""سجلات التشغيل والأخطاء — المرحلة 8."""

from __future__ import annotations

import logging
from pathlib import Path

from config.settings import BASE_DIR

LOG_DIR = BASE_DIR / "storage" / "logs"
_CONFIGURED = False
_db_sink = None


def set_db_log_sink(sink) -> None:
    global _db_sink
    _db_sink = sink


def setup_operations_logging(log_level: str = "INFO") -> Path:
    """تهيئة ملفات السجل في storage/logs/."""
    global _CONFIGURED

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    error_log = LOG_DIR / "errors.log"

    if not _CONFIGURED:
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

        error_handler = logging.FileHandler(error_log, encoding="utf-8")
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(fmt)

        ops_handler = logging.FileHandler(LOG_DIR / "operations.log", encoding="utf-8")
        ops_handler.setLevel(logging.INFO)
        ops_handler.setFormatter(fmt)

        root = logging.getLogger()
        root.addHandler(error_handler)
        root.addHandler(ops_handler)
        _CONFIGURED = True

    logging.getLogger().setLevel(getattr(logging, log_level.upper(), logging.INFO))
    return error_log


def log_operation(message: str) -> None:
    logging.getLogger("operations").info(message)
    if _db_sink is not None:
        _db_sink("INFO", message)
    try:
        from operations.report_archive import log_bot_activity

        text = message if len(message) <= 500 else message[:500] + "…"
        log_bot_activity("operation", message=text)
    except Exception:
        pass


def log_error(message: str, *, exc: BaseException | None = None) -> None:
    logger = logging.getLogger("operations")
    if exc is not None:
        logger.error("%s: %s", message, exc, exc_info=exc)
    else:
        logger.error(message)
    payload = message if exc is None else f"{message}: {exc}"
    if _db_sink is not None:
        _db_sink("ERROR", payload)
    try:
        from operations.report_archive import log_bot_activity

        text = payload if len(payload) <= 500 else payload[:500] + "…"
        log_bot_activity("error", message=text)
    except Exception:
        pass
