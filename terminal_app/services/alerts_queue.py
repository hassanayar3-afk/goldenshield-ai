"""تنبيهات Mobile + أجهزة + تخزين JSON."""

from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from terminal_app.config import ALERTS_FILE, DEVICES_FILE

_lock = threading.Lock()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def devices() -> dict:
    return load_json(DEVICES_FILE, {"devices": {}})


def save_devices(data: dict) -> None:
    save_json(DEVICES_FILE, data)


def prune_devices(data: dict, max_devices: int = 8) -> dict:
    """أبقِ أحدث الأجهزة فقط — يمنع تراكم التوكنات الميتة."""
    device_map = dict(data.get("devices") or {})
    if len(device_map) <= max_devices:
        return data
    ranked = sorted(
        device_map.items(),
        key=lambda kv: (
            str((kv[1] or {}).get("last_seen") or ""),
            str((kv[1] or {}).get("paired_at") or ""),
        ),
        reverse=True,
    )
    trimmed = dict(data)
    trimmed["devices"] = dict(ranked[:max_devices])
    trimmed["pruned_at"] = utc()
    trimmed["max_devices"] = max_devices
    return trimmed


def alerts() -> list:
    return load_json(ALERTS_FILE, [])


def push_alert(
    kind: str,
    title: str,
    body: str,
    *,
    level: str = "info",
    meta: dict | None = None,
) -> None:
    with _lock:
        items = alerts()
        items.append(
            {
                "id": secrets.token_hex(8),
                "ts": utc(),
                "kind": kind,
                "title": title,
                "body": body,
                "level": level,
                "meta": meta or {},
                "tone": True,
            }
        )
        save_json(ALERTS_FILE, items[-200:])
