from execution.correlation_filter import CorrelationFilter
from execution.dark_pool_splitter import split_order
from execution.trade_executor import TradeExecutor
from core.analyzer import AnalysisResult


def test_correlation_blocks_second_symbol_in_group():
    filt = CorrelationFilter(groups=(("BTC/USDT", "ETH/USDT"),))
    allowed, reason = filt.can_open("ETH/USDT", {"BTC/USDT"})
    assert allowed is False
    assert "BTC/USDT" in reason


def test_correlation_allows_unrelated_symbol():
    filt = CorrelationFilter(groups=(("BTC/USDT", "ETH/USDT"),))
    allowed, _ = filt.can_open("BNB/USDT", {"BTC/USDT"})
    assert allowed is True


def test_dark_pool_splits_large_order():
    chunks = split_order(amount=2.0, price=1000.0, max_chunk_usdt=500.0)
    assert len(chunks) > 1
    assert abs(sum(chunks) - 2.0) < 0.01


def test_trade_executor_rejects_low_score():
    executor = TradeExecutor()
    result = AnalysisResult(
        symbol="BTC/USDT",
        signal="WAIT",
        price=100.0,
        sma=99.0,
        score=5,
        passed=False,
        reasons=("درجة منخفضة",),
    )
    exec_result = executor.try_open(result)
    assert exec_result.executed is False
    assert exec_result.rejected is True


def test_manual_entry_bypasses_max_concurrent(monkeypatch):
    """اليدوي بلا سقف العدد؛ التلقائي يبقى على max_concurrent."""
    from execution.models.order import OrderSide
    from execution.models.trade import Position
    from risk.risk_orchestrator import RiskApproval

    executor = TradeExecutor()
    for i in range(12):
        executor.position_manager.add(
            Position(
                symbol=f"T{i}/USDT",
                side=OrderSide.BUY,
                entry_price=1.0,
                amount=1.0,
                stop_loss=0.9,
                take_profit=1.1,
            )
        )

    monkeypatch.setattr(
        executor.risk,
        "check_control_gates",
        lambda balance: RiskApproval(True, "ok"),
    )
    real_settings = __import__("config.settings", fromlist=["get_settings"]).get_settings()

    class _S:
        def __getattr__(self, name):
            if name == "max_concurrent_positions":
                return 12
            if name == "manual_max_concurrent_positions":
                return 0
            return getattr(real_settings, name)

    monkeypatch.setattr("execution.trade_executor.get_settings", lambda: _S())

    auto = AnalysisResult(
        symbol="NEW/USDT",
        signal="BUY SIGNAL",
        price=100.0,
        sma=99.0,
        score=10,
        passed=True,
        reasons=("auto",),
    )
    blocked = executor.try_open(auto, manual_force=False)
    assert blocked.executed is False
    assert "الحد الأقصى" in (blocked.reason or blocked.message)

    from execution.models.trade import ExecutionResult

    def _fake_execute(self, result, **kwargs):
        return ExecutionResult(
            executed=True,
            symbol=result.symbol,
            message="manual ok",
            rejected=False,
            reason="",
        )

    monkeypatch.setattr(TradeExecutor, "_execute_entry", _fake_execute)
    manual = executor.try_open(auto, manual_force=True)
    assert manual.executed is True
