from core.analyzer import AnalysisResult
from audit.snapshot_recorder import SnapshotRecorder


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


def test_snapshot_recorder_stores_market_state():
    recorder = SnapshotRecorder()
    result = _qualified_result()

    snapshot = recorder.record(result)

    assert snapshot.symbol == "BTC/USDT"
    assert snapshot.price == 100.0
    assert snapshot.score == 9
    assert snapshot.signal == "BUY SIGNAL"
    assert len(recorder.snapshots) == 1
    assert recorder.get(snapshot.id) == snapshot


def test_snapshot_recorder_multiple_symbols():
    recorder = SnapshotRecorder()
    recorder.record(_qualified_result())
    recorder.record(
        AnalysisResult(
            symbol="ETH/USDT",
            signal="WAIT",
            price=50.0,
            sma=48.0,
            score=5,
            passed=False,
            reasons=("انتظار",),
        )
    )
    assert len(recorder.snapshots) == 2
