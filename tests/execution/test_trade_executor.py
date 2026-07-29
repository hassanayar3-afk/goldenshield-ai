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


def test_trade_executor_opens_paper_trade_on_qualified_signal(monkeypatch):
    from risk.risk_orchestrator import RiskApproval

    monkeypatch.setattr(
        "execution.trade_executor.TradeExecutor._execute_entry",
        TradeExecutor._execute_entry,
    )
    executor = TradeExecutor()
    monkeypatch.setattr(
        executor.risk,
        "check_control_gates",
        lambda balance: RiskApproval(True, "ok"),
    )
    # تجنّب استدعاء دفتر حي أثناء الاختبار
    monkeypatch.setattr(
        "data.orderbook_fetcher.OrderBookFetcher.fetch",
        lambda self, symbol, **kwargs: (_ for _ in ()).throw(RuntimeError("skip book")),
    )
    result = AnalysisResult(
        symbol="BTC/USDT",
        signal="BUY SIGNAL",
        price=100.0,
        sma=99.0,
        score=9,
        passed=True,
        reasons=("مؤهل",),
    )
    exec_result = executor.try_open(result)
    assert exec_result.executed is True
    assert executor.position_manager.has("BTC/USDT")
