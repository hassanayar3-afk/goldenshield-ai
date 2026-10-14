"""Commander 1 — SMC macro (1H/4H), bound to neural matrix."""

from __future__ import annotations

from engines.smc_macro.engine import SMCMacroEngine

_ENGINE = SMCMacroEngine()


def evaluate(symbol: str):
    return _ENGINE.evaluate(symbol)
