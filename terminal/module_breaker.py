"""Circuit Breaker v2 — إيقاف قسم واحد بعد خسارتين متتاليتين."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ModuleBreakerState:
    consecutive_losses: int = 0
    halted_until: str | None = None


def _state_path() -> Path:
    root = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", ".")).resolve()
    if not root.is_dir():
        root = Path.cwd()
    p = root / "storage" / "runtime" / "module_breakers.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> dict[str, dict]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict[str, dict]) -> None:
    try:
        _state_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def is_module_halted(commander: str) -> bool:
    row = _load().get(commander) or {}
    until = row.get("halted_until")
    if not until:
        return False
    try:
        end = datetime.fromisoformat(until.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < end
    except Exception:
        return False


def record_module_trade_result(commander: str, pnl: float, *, cooldown_minutes: int = 30) -> None:
    data = _load()
    row = data.get(commander) or {"consecutive_losses": 0, "halted_until": None}
    if pnl < 0:
        row["consecutive_losses"] = int(row.get("consecutive_losses", 0)) + 1
    else:
        row["consecutive_losses"] = 0
        row["halted_until"] = None
    if int(row["consecutive_losses"]) >= 2:
        from datetime import timedelta

        end = datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)
        row["halted_until"] = end.isoformat()
        row["consecutive_losses"] = 0
    data[commander] = row
    _save(data)


def daily_clean_slate_reset() -> None:
    """تصفير مؤشرات اليوم — يُستدعى عند تغيّر يوم الجلسة."""
    try:
        _save({})
    except Exception:
        pass
