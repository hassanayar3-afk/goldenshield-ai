"""Runtime pause flag for UI / control service (engines skip new entries when paused)."""

from __future__ import annotations

_engines_paused: bool = False


def engines_paused() -> bool:
    return _engines_paused


def set_engines_paused(value: bool) -> None:
    global _engines_paused
    _engines_paused = value
