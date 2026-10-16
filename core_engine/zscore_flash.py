"""Commander 2 — Z-Score flash scalp (1m/5m)."""

from __future__ import annotations

from gold_flash.core import GoldFlashEngine

_ENGINE = GoldFlashEngine()


def evaluate(symbol: str):
    return _ENGINE.evaluate(symbol)
