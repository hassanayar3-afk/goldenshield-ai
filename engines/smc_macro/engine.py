"""القائد الأول — SMC & Macro (4h/1h/15m) مع ذاكرة HTF."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.analyzer import MarketAnalyzer
from data.htf_candle_cache import HTFCandleCache
from terminal.module_breaker import is_module_halted

logger = logging.getLogger(__name__)
_COMMANDER = "smc_macro"


@dataclass(frozen=True)
class CommanderProposal:
    commander: str
    symbol: str
    side: str
    price: float
    score: int
    signal: str
    reasons: tuple[str, ...]
    passed: bool


class SMCMacroEngine:
    def __init__(self) -> None:
        self._htf = HTFCandleCache()

    def evaluate(self, symbol: str) -> CommanderProposal | None:
        if is_module_halted(_COMMANDER):
            return None
        try:
            self._htf.touch(symbol)
            result = MarketAnalyzer(symbol=symbol).analyze()
            if result.price <= 0 or result.halted:
                return None
            if result.signal not in {"BUY SIGNAL", "SELL SIGNAL"} or not result.passed:
                return None
            side = "sell" if result.signal == "SELL SIGNAL" else "buy"
            return CommanderProposal(
                commander=_COMMANDER,
                symbol=symbol,
                side=side,
                price=result.price,
                score=int(result.score),
                signal=result.signal,
                reasons=tuple(result.reasons or ()),
                passed=bool(result.passed),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("smc_macro %s: %s", symbol, exc)
            return None
