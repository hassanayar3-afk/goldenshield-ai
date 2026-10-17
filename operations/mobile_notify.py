"""تنبيهات تطبيق الهاتف — قناة واحدة مشتركة مع Mobile API."""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(r"C:\GoldenShield_Binance\storage\runtime")
ALERTS_FILE = RUNTIME / "mobile_alerts.json"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def mobile_notify_only() -> bool:
    """True = التطبيق فقط، لا بث لتيليجرام."""
    for key in ("TELEGRAM_MUTE_ALL", "TELEGRAM_OUTBOUND_DISABLED", "MOBILE_NOTIFY_ONLY"):
        if os.getenv(key, "").strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return False


def push_mobile_alert(
    kind: str,
    title: str,
    body: str,
    *,
    level: str = "info",
    meta: dict | None = None,
) -> None:
    """أضف تنبيهاً يلتقطه Mobile API / التطبيق عبر /api/heartbeat."""
    try:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        items: list = []
        if ALERTS_FILE.exists():
            try:
                items = json.loads(ALERTS_FILE.read_text(encoding="utf-8"))
                if not isinstance(items, list):
                    items = []
            except Exception:
                items = []
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
        ALERTS_FILE.write_text(
            json.dumps(items[-200:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
