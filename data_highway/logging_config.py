"""
Central logging for Saqr: rotating files (10MB × 3) and bounded in-memory rings.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Deque, Dict

_LOGGERS: Dict[str, logging.Logger] = {}
_RING_BUFFERS: Dict[str, Deque[str]] = {}
_RING_MAXLEN = 1000


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def get_log_ring(name: str = "saqr") -> Deque[str]:
    """Return the bounded deque ring for a logger namespace (UI / WS tail)."""
    if name not in _RING_BUFFERS:
        _RING_BUFFERS[name] = deque(maxlen=_RING_MAXLEN)
    return _RING_BUFFERS[name]


class _RingHandler(logging.Handler):
    """Mirror formatted log lines into a fixed-size deque."""

    def __init__(self, ring: Deque[str]) -> None:
        super().__init__()
        self._ring = ring

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._ring.append(self.format(record))
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "saqr") -> logging.Logger:
    """
    Idempotent logger factory: console + rotating file + in-memory ring.
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = _env_int("LOG_MAX_BYTES", 10 * 1024 * 1024)
    backup_count = _env_int("LOG_BACKUP_COUNT", 3)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        log_dir / f"{name}.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    ring = get_log_ring(name)
    ring_handler = _RingHandler(ring)
    ring_handler.setFormatter(fmt)
    logger.addHandler(ring_handler)

    _LOGGERS[name] = logger
    return logger
