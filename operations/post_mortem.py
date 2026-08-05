# -*- coding: utf-8 -*-
"""Post-Mortem Engine — تشريح صفقة بعد الإغلاق (ملف + فهرس JSONL للتكيّف)."""

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


def _reports_root() -> Path:
    return Path(os.getcwd()) / "storage" / "reports" / "post_mortem"


def record_post_mortem(trade: dict[str, Any]) -> str | None:
    """يحفظ تشريحاً فردياً + يُلحق بسجل تكيّفي index.jsonl دون مسح DB."""
    if not _active():
        return None
    try:
        root = _reports_root()
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
            "amount": trade.get("amount"),
            "reason": trade.get("reason") or trade.get("close_reason"),
            "pipeline": trade.get("pipeline") or "enterprise",
            "ssot_matched": trade.get("ssot_matched"),
            "position_id": trade.get("position_id"),
            "outcome": (
                "win"
                if float(trade.get("pnl") or 0) > 0
                else ("loss" if float(trade.get("pnl") or 0) < 0 else "flat")
            ),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        index = root / "index.jsonl"
        with index.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return str(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_post_mortem: %s", exc)
        return None


def record_close_post_mortem(
    *,
    symbol: str,
    side: str,
    entry: float,
    exit_price: float,
    pnl: float,
    reason: str,
    score: int = 0,
    amount: float = 0.0,
    position_id: str = "",
    ssot_matched: bool | None = None,
) -> str | None:
    """واجهة مريحة تُستدعى من منفّذ الإغلاق."""
    try:
        return record_post_mortem(
            {
                "symbol": symbol,
                "side": side,
                "entry": float(entry or 0.0),
                "exit": float(exit_price or 0.0),
                "pnl": float(pnl or 0.0),
                "reason": reason,
                "score": int(score or 0),
                "amount": float(amount or 0.0),
                "position_id": position_id,
                "ssot_matched": ssot_matched,
                "pipeline": "enterprise",
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_close_post_mortem: %s", exc)
        return None
