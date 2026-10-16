"""درع الارتباط — منع صفقة جديدة إذا ارتباط > 75% مع مركز مفتوح."""

from __future__ import annotations

from dataclasses import dataclass

from execution.models.trade import Position


@dataclass(frozen=True)
class CorrelationDecision:
    allowed: bool
    reason: str


# مجموعات ارتباط تقريبية — توسعة لاحقة عبر series
_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"BTC/USDT", "ETH/USDT", "BNB/USDT"}),
    frozenset({"SOL/USDT", "AVAX/USDT", "DOT/USDT"}),
    frozenset({"XRP/USDT", "ADA/USDT", "TRX/USDT"}),
)


def _same_group(a: str, b: str) -> bool:
    for g in _GROUPS:
        if a in g and b in g:
            return True
    return False


def evaluate_correlation_shield(
    symbol: str,
    side: str,
    open_positions: list[Position],
    *,
    threshold: float = 0.75,
) -> CorrelationDecision:
    side_l = side.lower()
    for pos in open_positions:
        if pos.symbol == symbol:
            return CorrelationDecision(False, f"مركز مفتوح على {symbol}")
        pos_side = "buy" if pos.side.value == "buy" else "sell"
        if pos_side != side_l:
            continue
        if _same_group(symbol, pos.symbol):
            return CorrelationDecision(
                False,
                f"Negative Correlation Shield: {symbol} ~ {pos.symbol} (>={threshold:.0%})",
            )
    return CorrelationDecision(True, "Correlation OK")
