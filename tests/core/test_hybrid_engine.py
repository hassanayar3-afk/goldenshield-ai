from unittest.mock import patch

from core.analyzer import AnalysisResult
from core.hybrid_engine import evaluate_hybrid
from core.market_halt import MarketHaltResult
from core.fundamental.news_filter import NewsFilterResult
from core.macro.bonds_monitor import BondsResult
from core.macro.vix_monitor import VIXResult


def _technical_result(*, passed: bool = True, signal: str = "BUY SIGNAL") -> AnalysisResult:
    return AnalysisResult(
        symbol="BTC/USDT",
        signal=signal,
        price=100.0,
        sma=95.0,
        score=9,
        passed=passed,
        reasons=("technical ok",),
    )


def _safe_halt() -> MarketHaltResult:
    return MarketHaltResult(
        halted=False,
        reason="stable",
        vix=VIXResult(20.0, False, True, "ok"),
        bonds=BondsResult(4.0, 0.1, False, True, "ok"),
        news=NewsFilterResult(True, "ok", None),
    )


@patch("core.hybrid_engine.detect_institutional_zones")
@patch("core.hybrid_engine.track_whales")
@patch("core.hybrid_engine.analyze_social_sentiment")
@patch("core.hybrid_engine.analyze_sentiment")
@patch("core.hybrid_engine.check_market_halt")
def test_hybrid_allows_when_all_layers_pass(
    mock_halt,
    mock_sentiment,
    mock_social,
    mock_whales,
    mock_institutional,
):
    from core.sentiment.sentiment_analyzer import SentimentBias, SentimentResult
    from core.sentiment.social_sentiment import SocialBias, SocialSentimentResult
    from core.liquidity.whale_tracker import WhaleTrackerResult
    from core.liquidity.institutional_zones import InstitutionalZonesResult

    mock_halt.return_value = _safe_halt()
    mock_sentiment.return_value = SentimentResult(
        SentimentBias.BULLISH, 45, "Neutral", False, "ok"
    )
    mock_social.return_value = SocialSentimentResult(
        SocialBias.NEUTRAL, None, None, None, "ok"
    )
    mock_whales.return_value = WhaleTrackerResult((), True, True, "whale")
    mock_institutional.return_value = InstitutionalZonesResult((), True, True, "inst")

    decision = evaluate_hybrid("BTC/USDT", _technical_result())
    assert decision.allowed is True
    assert decision.final_signal == "BUY SIGNAL"
    assert decision.halted is False


@patch("core.hybrid_engine.detect_institutional_zones")
@patch("core.hybrid_engine.track_whales")
@patch("core.hybrid_engine.analyze_social_sentiment")
@patch("core.hybrid_engine.analyze_sentiment")
@patch("core.hybrid_engine.check_market_halt")
def test_hybrid_allows_sell_when_layers_pass(
    mock_halt,
    mock_sentiment,
    mock_social,
    mock_whales,
    mock_institutional,
):
    from core.sentiment.sentiment_analyzer import SentimentBias, SentimentResult
    from core.sentiment.social_sentiment import SocialBias, SocialSentimentResult
    from core.liquidity.whale_tracker import WhaleTrackerResult
    from core.liquidity.institutional_zones import InstitutionalZonesResult

    mock_halt.return_value = _safe_halt()
    mock_sentiment.return_value = SentimentResult(
        SentimentBias.BEARISH, 45, "Bearish", False, "ok"
    )
    mock_social.return_value = SocialSentimentResult(
        SocialBias.NEUTRAL, None, None, None, "ok"
    )
    mock_whales.return_value = WhaleTrackerResult((), False, True, "ask whale")
    mock_institutional.return_value = InstitutionalZonesResult((), False, True, "ask cluster")

    decision = evaluate_hybrid("BTC/USDT", _technical_result(signal="SELL SIGNAL"))
    assert decision.allowed is True
    assert decision.final_signal == "SELL SIGNAL"
    assert decision.halted is False


@patch("core.hybrid_engine.check_market_halt")
def test_hybrid_halts_on_vix(mock_halt):
    mock_halt.return_value = MarketHaltResult(
        halted=True,
        reason="VIX high",
        vix=VIXResult(35.0, True, False, "VIX high"),
        bonds=BondsResult(4.0, 0.1, False, True, "ok"),
        news=NewsFilterResult(True, "ok", None),
    )

    decision = evaluate_hybrid("BTC/USDT", _technical_result())
    assert decision.halted is True
    assert decision.final_signal == "HALTED"
    assert decision.allowed is False
