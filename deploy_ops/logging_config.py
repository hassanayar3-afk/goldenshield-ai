"""Rotating logs + bounded deques (Phase 6)."""

from __future__ import annotations

import gc
import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path


def official_root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    p = Path(raw)
    return p if p.is_dir() else Path.cwd()


def bounded_deque(maxlen: int | None = None) -> deque:
    n = maxlen if maxlen is not None else int(os.getenv("GS_MEMORY_DEQUE_MAX", "1000") or 1000)
    return deque(maxlen=max(100, min(n, 10000)))


def configure_sovereign_logging(name: str = "goldenshield") -> logging.Logger:
    log = logging.getLogger(name)
    if getattr(log, "_gs_sovereign_configured", False):
        return log
    root = official_root()
    log_dir = root / "storage" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = int(os.getenv("GS_LOG_MAX_BYTES", str(10 * 1024 * 1024)) or (10 * 1024 * 1024))
    backup = int(os.getenv("GS_LOG_BACKUP_COUNT", "3") or 3)
    path = log_dir / f"{name}.log"
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    if os.getenv("GS_LOG_GC_ON_ROTATE", "true").lower() in {"1", "true", "yes"}:
        def _gc_on_rotate(*_args: object) -> None:
            try:
                gc.collect()
            except Exception:
                pass

        handler.rotator = lambda _s, _d: None  # type: ignore[attr-defined]
        handler.namer = lambda x: x  # type: ignore[attr-defined]
        logging.getLogger().addHandler(handler)
    log._gs_sovereign_configured = True  # type: ignore[attr-defined]
    return log
