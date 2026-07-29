from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
CALENDAR_PATH = CONFIG_DIR / "economic_calendar.yaml"


class NewsImpact(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class EconomicEvent:
    name: str
    impact: NewsImpact
    scheduled_utc: datetime


def _parse_event(raw: dict) -> EconomicEvent | None:
    name = raw.get("name")
    impact_raw = str(raw.get("impact", "low")).lower()
    scheduled = raw.get("scheduled_utc")

    if not name or not scheduled:
        return None

    try:
        impact = NewsImpact(impact_raw)
    except ValueError:
        impact = NewsImpact.LOW

    scheduled_dt = datetime.fromisoformat(str(scheduled).replace("Z", "+00:00"))
    if scheduled_dt.tzinfo is None:
        scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)

    return EconomicEvent(name=name, impact=impact, scheduled_utc=scheduled_dt)


def fetch_economic_events(calendar_path: Path = CALENDAR_PATH) -> list[EconomicEvent]:
    events = _load_local_events(calendar_path)
    events.extend(_fetch_remote_events(calendar_path))
    return sorted(events, key=lambda event: event.scheduled_utc)


def _load_local_events(calendar_path: Path) -> list[EconomicEvent]:
    if not calendar_path.exists():
        return []

    with calendar_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    events: list[EconomicEvent] = []
    for raw in data.get("events", []):
        if not isinstance(raw, dict):
            continue
        parsed = _parse_event(raw)
        if parsed is not None:
            events.append(parsed)
    return events


def _fetch_remote_events(calendar_path: Path) -> list[EconomicEvent]:
    """جلب أحداث إضافية من رابط YAML اختياري (remote_feed_url)."""
    if not calendar_path.exists():
        return []

    with calendar_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    feed_url = data.get("remote_feed_url")
    if not feed_url:
        return []

    try:
        import requests

        response = requests.get(str(feed_url), timeout=12)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    events: list[EconomicEvent] = []
    for raw in payload.get("events", []):
        if not isinstance(raw, dict):
            continue
        parsed = _parse_event(raw)
        if parsed is not None:
            events.append(parsed)
    return events
