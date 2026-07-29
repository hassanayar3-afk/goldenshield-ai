"""محرك التحليل الفني — SMC, FVG, Volume, Mean Reversion."""

from core.technical.fvg_detector import FVGResult, detect_fvg
from core.technical.indicators import atr, rsi, sma
from core.technical.manipulation_guard import ManipulationGuardResult, detect_manipulation
from core.technical.mean_reversion import MeanReversionResult, analyze_mean_reversion
from core.technical.signal_scorer import ScoreBreakdown, is_trade_allowed, score_signal
from core.technical.smc_analyzer import SMCResult, analyze_smc
from core.technical.spread_filter import SpreadFilterResult, check_spread
from core.technical.timeframe_aligner import TimeframeAlignment, align_timeframes
from core.technical.volume_analyzer import VolumeAnalysis, analyze_volume

__all__ = [
    "FVGResult",
    "ManipulationGuardResult",
    "MeanReversionResult",
    "SMCResult",
    "ScoreBreakdown",
    "SpreadFilterResult",
    "TimeframeAlignment",
    "VolumeAnalysis",
    "align_timeframes",
    "analyze_mean_reversion",
    "analyze_smc",
    "analyze_volume",
    "atr",
    "check_spread",
    "detect_fvg",
    "detect_manipulation",
    "is_trade_allowed",
    "rsi",
    "score_signal",
    "sma",
]
