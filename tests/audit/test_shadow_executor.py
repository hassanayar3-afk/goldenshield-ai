from unittest.mock import patch

from core.analyzer import AnalysisResult
from audit.consensus_gate import check_consensus
from audit.shadow_executor import evaluate_shadow, run_liquidity_shadow, run_technical_shadow


def _qualified_result() -> AnalysisResult:
    return AnalysisResult(
        symbol="BTC/USDT",
        signal="BUY SIGNAL",
        price=100.0,
        sma=95.0,
        score=9,
        passed=True,
        reasons=("مؤهل",),
    )


def test_technical_shadow_approves_qualified_signal():
    vote = run_technical_shadow(_qualified_result())
    assert vote.approved is True
    assert vote.algorithm == "technical"


def test_technical_shadow_rejects_low_score():
    result = AnalysisResult(
        symbol="BTC/USDT",
        signal="WAIT",
        price=100.0,
        sma=95.0,
        score=5,
        passed=False,
        reasons=("ضعيف",),
    )
    vote = run_technical_shadow(result)
    assert vote.approved is False


@patch("audit.shadow_executor.detect_institutional_zones")
@patch("audit.shadow_executor.track_whales")
def test_liquidity_shadow_approves_with_whale_support(mock_whales, mock_institutional):
    from core.liquidity.institutional_zones import InstitutionalZonesResult
    from core.liquidity.whale_tracker import WhaleTrackerResult

    mock_whales.return_value = WhaleTrackerResult((), True, True, "whale support")
    mock_institutional.return_value = InstitutionalZonesResult((), False, False, "no cluster")

    vote = run_liquidity_shadow("BTC/USDT")
    assert vote.approved is True


@patch("audit.shadow_executor.detect_institutional_zones")
@patch("audit.shadow_executor.track_whales")
def test_shadow_consensus_requires_both_algorithms(mock_whales, mock_institutional):
    from core.liquidity.institutional_zones import InstitutionalZonesResult
    from core.liquidity.whale_tracker import WhaleTrackerResult

    mock_whales.return_value = WhaleTrackerResult((), True, True, "whale support")
    mock_institutional.return_value = InstitutionalZonesResult((), True, True, "bid cluster")

    shadow = evaluate_shadow(_qualified_result())
    consensus = check_consensus(shadow)

    assert shadow.consensus is True
    assert consensus.approved is True


@patch("audit.shadow_executor.detect_institutional_zones")
@patch("audit.shadow_executor.track_whales")
@patch("audit.shadow_executor.get_settings")
def test_shadow_consensus_rejects_without_liquidity(mock_settings, mock_whales, mock_institutional):
    from types import SimpleNamespace

    from core.liquidity.institutional_zones import InstitutionalZonesResult
    from core.liquidity.whale_tracker import WhaleTrackerResult

    mock_settings.return_value = SimpleNamespace(trial_mode=False)
    mock_whales.return_value = WhaleTrackerResult((), False, False, "no whales")
    mock_institutional.return_value = InstitutionalZonesResult((), False, False, "no cluster")

    shadow = evaluate_shadow(_qualified_result())
    consensus = check_consensus(shadow)

    assert shadow.consensus is False
    assert consensus.approved is False
