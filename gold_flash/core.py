"""حلقة gold_flash 2.0 — معزولة بالكامل عن SMC/Momentum."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

from data.ohlcv_fetcher import OHLCVFetcher
from data.ticker_fetcher import TickerFetcher
from gold_flash.analytics import evaluate_flash_analytics
from gold_flash.filters import candle_confirmation_guard, smart_slippage_breaker
from gold_flash.risk_execution import evaluate_fee_aware_tp1
from terminal.module_breaker import is_module_halted
from terminal.scoring import confidence_percent

logger = logging.getLogger(__name__)

_COMMANDER = "gold_flash"


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


class GoldFlashEngine:
    def __init__(self) -> None:
        self._closes: dict[str, deque[float]] = {}
        self._ohlcv = OHLCVFetcher()
        self._ticker = TickerFetcher()

    def _closes_for(self, symbol: str) -> deque[float]:
        if symbol not in self._closes:
            self._closes[symbol] = deque(maxlen=120)
        return self._closes[symbol]

    def evaluate(self, symbol: str) -> CommanderProposal | None:
        if is_module_halted(_COMMANDER):
            return None
        try:
            candles = self._ohlcv.fetch(symbol, "5m", limit=30)
            closes = self._closes_for(symbol)
            for c in candles:
                closes.append(float(c.close))
            ticker = self._ticker.fetch(symbol)
            price = float(ticker.last)
            flash = evaluate_flash_analytics(closes)
            if flash is None:
                return None

            spread_pct = abs(ticker.ask - ticker.bid) / price * 100 if price > 0 else 99
            slip = smart_slippage_breaker(
                spread_pct=spread_pct,
                bid_depth_usdt=float(getattr(ticker, "bid_volume", 0) or 0) * price,
                ask_depth_usdt=float(getattr(ticker, "ask_volume", 0) or 0) * price,
            )
            if not slip.allowed:
                return None

            prev = closes[-2] if len(closes) >= 2 else price
            candle = candle_confirmation_guard(
                prev_close=prev, last_close=price, side=flash.side
            )
            if not candle.allowed:
                return None

            # درجة داخلية 8–9 حسب قوة Z
            z_abs = abs(flash.z_score)
            raw_score = 8 if z_abs < 2.5 else 9
            conf = confidence_percent(raw_score)
            tp1 = price * (1.01 if flash.side == "buy" else 0.99)
            plan = evaluate_fee_aware_tp1(entry=price, tp1=tp1, amount=0.01)
            if not plan.approved:
                return None

            signal = "BUY SIGNAL" if flash.side == "buy" else "SELL SIGNAL"
            reasons = (flash.reason, slip.reason, candle.reason, plan.reason)
            return CommanderProposal(
                commander=_COMMANDER,
                symbol=symbol,
                side=flash.side,
                price=price,
                score=raw_score,
                signal=signal,
                reasons=reasons,
                passed=conf >= 70,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("gold_flash %s: %s", symbol, exc)
            return None
