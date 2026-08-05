from __future__ import annotations

import logging

from dataclasses import dataclass

from core.constants import ANALYSIS_TIMEFRAMES, OHLCV_ANALYSIS_LIMIT
from core.hybrid_engine import HybridDecision, evaluate_hybrid
from core.technical.fvg_detector import detect_fvg
from core.technical.manipulation_guard import detect_manipulation
from core.technical.mean_reversion import analyze_mean_reversion
from core.technical.micro_entry import evaluate_micro_entry
from core.technical.quality_gates import run_quality_gates
from core.technical.signal_scorer import ScoreBreakdown, is_trade_allowed, score_signal
from core.technical.smc_analyzer import analyze_smc
from core.technical.spread_filter import check_spread
from core.technical.timeframe_aligner import TimeframeAlignment, TrendDirection, align_timeframes
from core.technical.volume_analyzer import analyze_volume
from data.ohlcv_fetcher import OHLCVFetcher
from data.orderbook_fetcher import OrderBookFetcher
from data.ticker_fetcher import TickerFetcher
from config.settings import get_settings
from core.micro_structure import analyze_orderbook_micro

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisResult:
    symbol: str
    signal: str
    price: float
    sma: float
    score: int
    passed: bool
    reasons: tuple[str, ...]
    halted: bool = False
    hybrid: HybridDecision | None = None
    alignment: TimeframeAlignment | None = None
    score_breakdown: ScoreBreakdown | None = None

    @property
    def is_buy(self) -> bool:
        return self.signal == "BUY SIGNAL"

    @property
    def is_sell(self) -> bool:
        return self.signal == "SELL SIGNAL"

    @property
    def is_entry_signal(self) -> bool:
        return self.is_buy or self.is_sell


class MarketAnalyzer:
    """Orchestrator — يجمع التحليل الفني + الذكاء الهجين."""

    def __init__(
        self,
        symbol: str,
        *,
        ohlcv_fetcher: OHLCVFetcher | None = None,
        ticker_fetcher: TickerFetcher | None = None,
    ) -> None:
        self.symbol = symbol
        self._ohlcv_fetcher = ohlcv_fetcher or OHLCVFetcher()
        self._ticker_fetcher = ticker_fetcher or TickerFetcher()

    def _run_technical(
        self,
        candles_by_tf: dict,
        ticker,
    ) -> tuple[ScoreBreakdown, TimeframeAlignment, float, bool, str]:
        alignment = align_timeframes(candles_by_tf)
        smc = analyze_smc(candles_by_tf.get("1h", []))
        fvg = detect_fvg(candles_by_tf.get("15m", []))
        volume = analyze_volume(candles_by_tf.get("1h", []))
        mean_reversion = analyze_mean_reversion(candles_by_tf.get("4h", []))
        spread = check_spread(ticker)
        manipulation = detect_manipulation(candles_by_tf.get("15m", []))

        score = score_signal(
            alignment=alignment,
            smc=smc,
            fvg=fvg,
            volume=volume,
            mean_reversion=mean_reversion,
            spread=spread,
            manipulation=manipulation,
        )

        allowed = is_trade_allowed(score, alignment, smc)
        sma_value = mean_reversion.sma_value or 0.0
        quality_reasons: list[str] = []

        if allowed and alignment.direction != TrendDirection.NEUTRAL:
            quality = run_quality_gates(
                candles_m15=candles_by_tf.get("15m", []),
                candles_h1=candles_by_tf.get("1h", []),
                candles_h4=candles_by_tf.get("4h", []),
                smc=smc,
                volume=volume,
                direction=alignment.direction,
                enabled=bool(getattr(get_settings(), "quality_gates_enabled", True)),
                volume_spike_multiplier=float(
                    getattr(get_settings(), "volume_spike_multiplier", 1.5)
                ),
            )
            quality_reasons.append(quality.reason)
            if not quality.passed:
                allowed = False

        # —— دخول مجهري 5m/1m (طبقة مضافة فوق الهرم 4H/1H/15m) ——
        if allowed and alignment.direction != TrendDirection.NEUTRAL:
            try:
                micro = evaluate_micro_entry(
                    candles_5m=candles_by_tf.get("5m", []),
                    candles_1m=candles_by_tf.get("1m", []),
                    direction=alignment.direction,
                )
                quality_reasons.append(f"مجهري: {micro.reason}")
                if not micro.ok:
                    allowed = False
            except Exception as micro_exc:  # noqa: BLE001
                logger.warning("micro entry %s: %s", self.symbol, micro_exc)

        # —— نبض دفتر الأوامر (Micro-Tick / Iceberg / Spoof) ——
        if allowed:
            try:
                book = OrderBookFetcher().fetch(self.symbol)
                ob = {
                    "bids": [(lvl.price, lvl.amount) for lvl in book.bids],
                    "asks": [(lvl.price, lvl.amount) for lvl in book.asks],
                }
                micro_ob = analyze_orderbook_micro(ob)
                quality_reasons.append(
                    f"دفتر: Δ={micro_ob.delta_proxy:.4g} iceberg={micro_ob.iceberg_suspect} spoof={micro_ob.spoof_suspect}"
                )
                if micro_ob.spoof_suspect:
                    allowed = False
                    quality_reasons.append("رفض: اشتباه Spoofing/جدار وهمي في الدفتر")
            except Exception as ob_exc:  # noqa: BLE001
                logger.debug("orderbook micro in analyzer: %s", ob_exc)

        if allowed and alignment.direction == TrendDirection.BULLISH:
            signal = "BUY SIGNAL"
        elif allowed and alignment.direction == TrendDirection.BEARISH:
            signal = "SELL SIGNAL"
        elif score.total == 0:
            signal = "REJECTED"
        else:
            signal = "WAIT"

        if quality_reasons:
            score = ScoreBreakdown(
                total=score.total,
                components=score.components,
                passed_minimum=score.passed_minimum and allowed,
                reasons=tuple(dict.fromkeys((*score.reasons, *quality_reasons))),
            )

        return score, alignment, sma_value, allowed, signal

    def analyze(self) -> AnalysisResult:
        try:
            candles_by_tf = self._ohlcv_fetcher.fetch_multi(
                self.symbol,
                timeframes=ANALYSIS_TIMEFRAMES,
                limit=OHLCV_ANALYSIS_LIMIT,
                use_cache=True,
            )
            ticker = self._ticker_fetcher.fetch(self.symbol)
            price = ticker.last

            score, alignment, sma_value, technical_passed, technical_signal = self._run_technical(
                candles_by_tf, ticker
            )

            technical_result = AnalysisResult(
                symbol=self.symbol,
                signal=technical_signal,
                price=price,
                sma=sma_value,
                score=score.total,
                passed=technical_passed,
                reasons=score.reasons,
                alignment=alignment,
                score_breakdown=score,
            )

            hybrid = evaluate_hybrid(
                self.symbol,
                technical_result,
                m15_candles=candles_by_tf.get("15m", []),
            )

            all_reasons = tuple(dict.fromkeys((*score.reasons, *hybrid.reasons)))

            return AnalysisResult(
                symbol=self.symbol,
                signal=hybrid.final_signal,
                price=price,
                sma=sma_value,
                score=score.total,
                passed=hybrid.allowed,
                reasons=all_reasons,
                halted=hybrid.halted,
                hybrid=hybrid,
                alignment=alignment,
                score_breakdown=score,
            )
        except Exception as exc:
            logger.exception("فشل تحليل %s", self.symbol)
            from data.symbol_routing import display_symbol, infer_data_source

            source = infer_data_source(self.symbol)
            return AnalysisResult(
                symbol=self.symbol,
                signal="ERROR",
                price=0.0,
                sma=0.0,
                score=0,
                passed=False,
                reasons=(
                    f"فشل جلب بيانات {display_symbol(self.symbol)} عبر {source}: {exc}",
                ),
            )
