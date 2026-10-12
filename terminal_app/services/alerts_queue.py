from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from terminal_app.config import (
    ALERTS_FILE,
    DB,
    DEVICES_FILE,
    MASTER_TOKEN,
    PAIR_CODE,
    PANEL_ROOT,
    ROOT,
    RUNTIME,
    STRATEGY_CODE,
)

_lock = threading.Lock()

def prune_devices(data: dict, max_devices: int = 8) -> dict:
    """أبقِ أحدث الأجهزة فقط — يمنع تراكم التوكنات الميتة (سبب unauthorized / طلب الرمز)."""
    devices = dict(data.get("devices") or {})
    if len(devices) <= max_devices:
        return data
    ranked = sorted(
        devices.items(),
        key=lambda kv: (
            str((kv[1] or {}).get("last_seen") or ""),
            str((kv[1] or {}).get("paired_at") or ""),
        ),
        reverse=True,
    )
    data = dict(data)
    data["devices"] = dict(ranked[:max_devices])
    data["pruned_at"] = _utc()
    data["max_devices"] = max_devices
    return data
def push_alert(kind: str, title: str, body: str, *, level: str = "info", meta: dict | None = None) -> None:
    with _lock:
        items = _alerts()
        items.append(
            {
                "id": secrets.token_hex(8),
                "ts": _utc(),
                "kind": kind,
                "title": title,
                "body": body,
                "level": level,
                "meta": meta or {},
                "tone": True,
            }
        )
        _save_json(ALERTS_FILE, items[-200:])
def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def save_devices(data: dict) -> None:
    _save_json(DEVICES_FILE, data)
def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default
def alerts() -> list:
    return _load_json(ALERTS_FILE, [])
def utc() -> str:
    return datetime.now(timezone.utc).isoformat()
def devices() -> dict:
    return _load_json(DEVICES_FILE, {"devices": {}})
