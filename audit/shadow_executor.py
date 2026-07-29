"""Shadow Execution — توافق خوارزميتين مستقلتين."""

from __future__ import annotations

from dataclasses import dataclass

from core.analyzer import AnalysisResult
from core.constants import meets_signal_minimum
from core.liquidity.institutional_zones import detect_institutional_zones
from core.liquidity.whale_tracker import track_whales
from config.settings import get_settings


@dataclass(frozen=True)
class ShadowVote:
    algorithm: str
    approved: bool
    reason: str


@dataclass(frozen=True)
class ShadowResult:
    symbol: str
    technical: ShadowVote
    liquidity: ShadowVote

    @property
    def consensus(self) -> bool:
        return self.technical.approved and self.liquidity.approved


def run_technical_shadow(result: AnalysisResult) -> ShadowVote:
    approved = (
        meets_signal_minimum(result.score)
        and result.passed
        and result.signal in {"BUY SIGNAL", "SELL SIGNAL"}
        and not result.halted
    )
    if approved:
        reason = f"فني: درجة {result.score}/10 + {result.signal}"
    else:
        reason = f"فني مرفوض: درجة {result.score} | {result.signal}"
    return ShadowVote(algorithm="technical", approved=approved, reason=reason)


def run_liquidity_shadow(symbol: str, *, signal: str = "BUY SIGNAL") -> ShadowVote:
    if get_settings().trial_mode:
        return ShadowVote(
            algorithm="liquidity",
            approved=True,
            reason="تجربة: مرور طبقة السيولة",
        )

    whales = track_whales(symbol)
    institutional = detect_institutional_zones(symbol, whale_result=whales)
    if signal == "SELL SIGNAL":
        approved = whales.has_whale_resistance or institutional.has_ask_cluster
    else:
        approved = whales.has_whale_support or institutional.has_bid_cluster
    if approved:
        reason = f"سيولة: {whales.reason} | {institutional.reason}"
    else:
        reason = f"سيولة غير كافية: {whales.reason} | {institutional.reason}"
    return ShadowVote(algorithm="liquidity", approved=approved, reason=reason)


def evaluate_shadow(result: AnalysisResult) -> ShadowResult:
    return ShadowResult(
        symbol=result.symbol,
        technical=run_technical_shadow(result),
        liquidity=run_liquidity_shadow(result.symbol, signal=result.signal),
    )
