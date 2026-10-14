"""Commander 3 — micro momentum IOC."""

from __future__ import annotations

from engines.micro_momentum.engine import MicroMomentumEngine

_ENGINE = MicroMomentumEngine()


def evaluate(symbol: str):
    return _ENGINE.evaluate(symbol)
