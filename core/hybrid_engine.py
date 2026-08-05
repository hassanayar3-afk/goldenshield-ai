from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from config.settings import get_settings
from core.liquidity.institutional_zones import detect_institutional_zones
from core.liquidity.whale_tracker import track_whales
from core.market_halt import check_market_halt
from core.sentiment.anomaly_detector import detect_sentiment_anomaly
from core.sentiment.sentiment_analyzer import SentimentBias, analyze_sentiment
from core.sentiment.social_sentiment import SocialBias, analyze_social_sentiment
from data.models.candle import Candle

if TYPE_CHECKING:
    from core.analyzer import AnalysisResult


def _apply_v13_market_filters(
    symbol: str,
    *,
    side: str,
    reasons: list[str],
) -> HybridDecision | None:
    """فلاتر v1.3 — تُرجع HybridDecision عند الرفض، وإلا None."""
    try:
        from core.market_filters_extra import (
            check_btc_dominance_filter,
            check_funding_guard,
            check_weekend_flat_policy,
            detect_spoofing,
        )
        from data.orderbook_fetcher import OrderBookFetcher

        weekend = check_weekend_flat_policy()
        reasons.append(weekend.reason)
        if not weekend.allowed:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="REJECTED",
                technical_passed=True,
                sentiment_ok=True,
                macro_ok=False,
                liquidity_ok=True,
                reasons=tuple(reasons),
            )

        funding = check_funding_guard(is_futures=False)
        reasons.append(funding.reason)
        if not funding.allowed:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="REJECTED",
                technical_passed=True,
                sentiment_ok=True,
                macro_ok=False,
                liquidity_ok=True,
                reasons=tuple(reasons),
            )

        dom = check_btc_dominance_filter(symbol, side=side)
        reasons.append(dom.reason)
        if not dom.allowed:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="WAIT",
                technical_passed=True,
                sentiment_ok=True,
                macro_ok=True,
                liquidity_ok=False,
                reasons=tuple(reasons),
            )

        try:
            book = OrderBookFetcher().fetch(symbol)
            bids = [(lvl.price, lvl.amount) for lvl in book.bids]
            asks = [(lvl.price, lvl.amount) for lvl in book.asks]
            spoof = detect_spoofing(bids, asks)
            reasons.append(spoof.reason)
            if not spoof.allowed:
                return HybridDecision(
                    allowed=False,
                    halted=False,
                    final_signal="REJECTED",
                    technical_passed=True,
                    sentiment_ok=True,
                    macro_ok=True,
                    liquidity_ok=False,
                    reasons=tuple(reasons),
                )
            # —— Micro-Tick / Iceberg عبر analyze_orderbook_micro (موصول حياً) ——
            try:
                from core.micro_structure import analyze_orderbook_micro

                micro = analyze_orderbook_micro({"bids": bids, "asks": asks})
                reasons.append(
                    f"microΔ={micro.delta_proxy:.4g} iceberg={micro.iceberg_suspect} spoof={micro.spoof_suspect}"
                )
                if micro.spoof_suspect:
                    return HybridDecision(
                        allowed=False,
                        halted=False,
                        final_signal="REJECTED",
                        technical_passed=True,
                        sentiment_ok=True,
                        macro_ok=True,
                        liquidity_ok=False,
                        reasons=tuple(reasons) + ("رفض دفتر: اشتباه Spoof/Iceberg",),
                    )
                # جدار Iceberg معاكس لاتجاه الصفقة
                if micro.iceberg_suspect:
                    if side == "buy" and micro.ask_wall > micro.bid_wall * 1.5:
                        return HybridDecision(
                            allowed=False,
                            halted=False,
                            final_signal="WAIT",
                            technical_passed=True,
                            sentiment_ok=True,
                            macro_ok=True,
                            liquidity_ok=False,
                            reasons=tuple(reasons) + ("جدار عرض Iceberg ضد الشراء",),
                        )
                    if side == "sell" and micro.bid_wall > micro.ask_wall * 1.5:
                        return HybridDecision(
                            allowed=False,
                            halted=False,
                            final_signal="WAIT",
                            technical_passed=True,
                            sentiment_ok=True,
                            macro_ok=True,
                            liquidity_ok=False,
                            reasons=tuple(reasons) + ("جدار طلب Iceberg ضد البيع",),
                        )
            except Exception as micro_exc:  # noqa: BLE001
                reasons.append(f"micro_structure تخطي: {micro_exc}")
        except Exception:
            pass
    except Exception:
        return None
    return None


@dataclass(frozen=True)
class HybridDecision:
    allowed: bool
    halted: bool
    final_signal: str
    technical_passed: bool
    sentiment_ok: bool
    macro_ok: bool
    liquidity_ok: bool
    reasons: tuple[str, ...]


def evaluate_hybrid(
    symbol: str,
    technical: "AnalysisResult",
    *,
    m15_candles: list[Candle] | None = None,
) -> HybridDecision:
    reasons: list[str] = []
    trial_mode = bool(get_settings().trial_mode)

    halt = check_market_halt()
    if halt.halted:
        return HybridDecision(
            allowed=False,
            halted=True,
            final_signal="HALTED",
            technical_passed=technical.passed,
            sentiment_ok=False,
            macro_ok=False,
            liquidity_ok=False,
            reasons=(halt.reason,),
        )

    reasons.append(halt.reason)

    sentiment = analyze_sentiment()
    reasons.append(sentiment.reason)

    social = analyze_social_sentiment(symbol)
    reasons.append(social.reason)

    if m15_candles and not trial_mode:
        anomaly = detect_sentiment_anomaly(m15_candles)
        reasons.append(anomaly.reason)
        if anomaly.detected:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="REJECTED",
                technical_passed=technical.passed,
                sentiment_ok=False,
                macro_ok=True,
                liquidity_ok=False,
                reasons=tuple(reasons),
            )

    whales = track_whales(symbol)
    institutional = detect_institutional_zones(symbol, whale_result=whales)
    reasons.append(whales.reason)
    reasons.append(institutional.reason)

    is_buy = technical.passed and technical.signal == "BUY SIGNAL"
    is_sell = technical.passed and technical.signal == "SELL SIGNAL"

    # مرحلة التجربة: لا تحوّل BUY/SELL التقني إلى WAIT بسبب Fear&Greed / Social
    if trial_mode and (is_buy or is_sell):
        if is_buy and sentiment.is_extreme and sentiment.bias == SentimentBias.BEARISH:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="REJECTED",
                technical_passed=True,
                sentiment_ok=False,
                macro_ok=True,
                liquidity_ok=True,
                reasons=(*reasons, "تجربة: رفض لأن المشاعر هابطة جداً"),
            )
        if is_sell and sentiment.is_extreme and sentiment.bias == SentimentBias.BULLISH:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="REJECTED",
                technical_passed=True,
                sentiment_ok=False,
                macro_ok=True,
                liquidity_ok=True,
                reasons=(*reasons, "تجربة: رفض لأن المشاعر صاعدة جداً"),
            )
        signal = "BUY SIGNAL" if is_buy else "SELL SIGNAL"
        return HybridDecision(
            allowed=True,
            halted=False,
            final_signal=signal,
            technical_passed=True,
            sentiment_ok=True,
            macro_ok=True,
            liquidity_ok=True,
            reasons=(*reasons, "تجربة: مرور هجين — فتح فني مؤهل"),
        )

    if is_buy:
        if sentiment.is_extreme and sentiment.bias == SentimentBias.BEARISH:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="REJECTED",
                technical_passed=True,
                sentiment_ok=False,
                macro_ok=True,
                liquidity_ok=False,
                reasons=tuple(reasons),
            )
        sentiment_ok = sentiment.bias != SentimentBias.BEARISH
        if social.bias == SocialBias.BEARISH:
            sentiment_ok = False
        liquidity_ok = whales.has_whale_support or institutional.has_bid_cluster
        if liquidity_ok and sentiment_ok:
            extra = _apply_v13_market_filters(symbol, side="buy", reasons=reasons)
            if extra is not None:
                return extra
            return HybridDecision(
                allowed=True,
                halted=False,
                final_signal="BUY SIGNAL",
                technical_passed=True,
                sentiment_ok=True,
                macro_ok=True,
                liquidity_ok=True,
                reasons=tuple(reasons),
            )
        return HybridDecision(
            allowed=False,
            halted=False,
            final_signal="WAIT",
            technical_passed=True,
            sentiment_ok=sentiment_ok,
            macro_ok=True,
            liquidity_ok=liquidity_ok,
            reasons=tuple(reasons),
        )

    if is_sell:
        if sentiment.is_extreme and sentiment.bias == SentimentBias.BULLISH:
            return HybridDecision(
                allowed=False,
                halted=False,
                final_signal="REJECTED",
                technical_passed=True,
                sentiment_ok=False,
                macro_ok=True,
                liquidity_ok=False,
                reasons=tuple(reasons),
            )
        sentiment_ok = sentiment.bias != SentimentBias.BULLISH
        if social.bias == SocialBias.BULLISH:
            sentiment_ok = False
        liquidity_ok = whales.has_whale_resistance or institutional.has_ask_cluster
        if liquidity_ok and sentiment_ok:
            extra = _apply_v13_market_filters(symbol, side="sell", reasons=reasons)
            if extra is not None:
                return extra
            return HybridDecision(
                allowed=True,
                halted=False,
                final_signal="SELL SIGNAL",
                technical_passed=True,
                sentiment_ok=True,
                macro_ok=True,
                liquidity_ok=True,
                reasons=tuple(reasons),
            )
        return HybridDecision(
            allowed=False,
            halted=False,
            final_signal="WAIT",
            technical_passed=True,
            sentiment_ok=sentiment_ok,
            macro_ok=True,
            liquidity_ok=liquidity_ok,
            reasons=tuple(reasons),
        )

    liquidity_ok = whales.has_whale_support or institutional.has_bid_cluster
    sentiment_ok = sentiment.bias != SentimentBias.BEARISH
    return HybridDecision(
        allowed=False,
        halted=False,
        final_signal=technical.signal,
        technical_passed=technical.passed,
        sentiment_ok=sentiment_ok,
        macro_ok=True,
        liquidity_ok=liquidity_ok,
        reasons=tuple(reasons),
    )
