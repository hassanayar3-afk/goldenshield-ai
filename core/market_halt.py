from __future__ import annotations

from dataclasses import dataclass

from core.fundamental.news_filter import NewsFilterResult, check_news_filter
from core.macro.bonds_monitor import BondsResult, check_bonds
from core.macro.vix_monitor import VIXResult, check_vix


@dataclass(frozen=True)
class MarketHaltResult:
    halted: bool
    reason: str
    vix: VIXResult
    bonds: BondsResult
    news: NewsFilterResult


def check_market_halt() -> MarketHaltResult:
    vix = check_vix()
    bonds = check_bonds()
    news = check_news_filter()

    if not news.trading_allowed:
        return MarketHaltResult(
            halted=True,
            reason=news.reason,
            vix=vix,
            bonds=bonds,
            news=news,
        )

    if not vix.is_safe:
        return MarketHaltResult(
            halted=True,
            reason=vix.reason,
            vix=vix,
            bonds=bonds,
            news=news,
        )

    if not bonds.is_safe:
        return MarketHaltResult(
            halted=True,
            reason=bonds.reason,
            vix=vix,
            bonds=bonds,
            news=news,
        )

    return MarketHaltResult(
        halted=False,
        reason="بيئة السوق مستقرة",
        vix=vix,
        bonds=bonds,
        news=news,
    )
