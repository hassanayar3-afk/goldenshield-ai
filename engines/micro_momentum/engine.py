"""القائد الثالث — زخم لحظي (أعلى 5 سيولة، IOC/WS book)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from data.ws_orderbook_mirror import get_orderbook_mirror
from data.ticker_fetcher import TickerFetcher
from terminal.module_breaker import is_module_halted

logger = logging.getLogger(__name__)
_COMMANDER = "micro_momentum"

DEFAULT_TOP5 = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT")


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


def _top_liquidity_symbols() -> tuple[str, ...]:
    raw = (os.getenv("MICRO_MOMENTUM_SYMBOLS") or "").strip()
    if raw:
        return tuple(s.strip() for s in raw.split(",") if s.strip())
    return DEFAULT_TOP5


class MicroMomentumEngine:
    def __init__(self) -> None:
        self._ticker = TickerFetcher()
        self._book = get_orderbook_mirror()

    def evaluate(self, symbol: str) -> CommanderProposal | None:
        if symbol not in _top_liquidity_symbols():
            return None
        if is_module_halted(_COMMANDER):
            return None
        try:
            self._book.ensure_stream(symbol)
            imbalance = self._book.imbalance(symbol)
            if imbalance is None:
                return None
            ticker = self._ticker.fetch(symbol)
            price = float(ticker.last)
            if price <= 0:
                return None
            side = "buy" if imbalance > 0.15 else "sell" if imbalance < -0.15 else ""
            if not side:
                return None
            signal = "BUY SIGNAL" if side == "buy" else "SELL SIGNAL"
            score = 9 if abs(imbalance) > 0.25 else 8
            return CommanderProposal(
                commander=_COMMANDER,
                symbol=symbol,
                side=side,
                price=price,
                score=score,
                signal=signal,
                reasons=(f"Book imbalance {imbalance:+.2f}", "WS in-memory mirror"),
                passed=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("micro_momentum %s: %s", symbol, exc)
            return None
