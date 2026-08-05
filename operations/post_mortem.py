# -*- coding: utf-8 -*-
"""Post-Mortem Engine — تشريح صفقة بعد الإغلاق (طبقة مضافة، لا تمس DB بخلاف التسجيل)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _active() -> bool:
    raw = (os.getenv("POST_MORTEM_ENGINE_ACTIVE", "true") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def record_post_mortem(trade: dict[str, Any]) -> str | None:
    """يحفظ ملخص تشريح في storage/reports/post_mortem/ دون حذف سجلات أخرى."""
    if not _active():
        return None
    try:
        root = Path(os.getcwd()) / "storage" / "reports" / "post_mortem"
        root.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        symbol = str(trade.get("symbol") or "UNK").replace("/", "")
        path = root / f"pm_{symbol}_{ts}.json"
        payload = {
            "ts": ts,
            "symbol": trade.get("symbol"),
            "side": trade.get("side"),
            "pnl": trade.get("pnl"),
            "score": trade.get("score"),
            "entry": trade.get("entry"),
            "exit": trade.get("exit"),
            "reason": trade.get("reason") or trade.get("close_reason"),
            "pipeline": trade.get("pipeline"),
            "ssot_matched": trade.get("ssot_matched"),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_post_mortem: %s", exc)
        return None
