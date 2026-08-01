"""اختبارات بوابة عمق السوق والأوزان والماكرو والتخارج."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from database.connection import init_database
from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.smart_exits import evaluate_multi_tier_tp
from intelligence.adaptive_weights import apply_weight_multipliers, soften_component_after_loss
from intelligence.shadow_store import ShadowStore
from risk.macro_flow_gate import evaluate_macro_flow_gate
from risk.orderbook_imbalance_gate import evaluate_orderbook_imbalance


def test_orderbook_gate_rejects_against_buy(monkeypatch) -> None:
    monkeypatch.setenv("ORDERBOOK_IMBALANCE_GATE_ENABLED", "true")
    monkeypatch.setenv("ORDERBOOK_IMBALANCE_MIN", "0.15")

    class FakeBook:
        bid_volume = 10.0
        ask_volume = 90.0

    class FakeFetcher:
        def fetch(self, symbol, depth=20):  # noqa: ARG002
            return FakeBook()

    monkeypatch.setattr(
        "data.orderbook_fetcher.OrderBookFetcher",
        FakeFetcher,
    )

    # import path used inside gate
    import risk.orderbook_imbalance_gate as gate

    monkeypatch.setattr(
        gate,
        "OrderBookFetcher",
        FakeFetcher,
        raising=False,
    )

    # Patch at call site inside function via module replacement
    import data.orderbook_fetcher as obf

    monkeypatch.setattr(obf, "OrderBookFetcher", FakeFetcher)

    result = evaluate_orderbook_imbalance("BTC/USDT", side="buy")
    assert result.approved is False
    assert result.imbalance < 0


def test_orderbook_gate_off_passes(monkeypatch) -> None:
    monkeypatch.setenv("ORDERBOOK_IMBALANCE_GATE_ENABLED", "false")
    result = evaluate_orderbook_imbalance("BTC/USDT", side="buy")
    assert result.approved is True


def test_adaptive_weights_soften(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ADAPTIVE_WEIGHTS_ENABLED", "true")
    monkeypatch.setenv("ADAPTIVE_WEIGHT_MAX_DELTA", "0.20")
    db = init_database(str(tmp_path / "w.db"))
    monkeypatch.setattr(
        "intelligence.adaptive_weights.ShadowStore",
        lambda: ShadowStore(db),
    )
    adj = soften_component_after_loss(reason="Stop Loss volume spike")
    assert "volume" in adj
    assert adj["volume"] < 1.0

    scaled = apply_weight_multipliers({"volume": 20, "smc": 5})
    assert scaled["volume"] < 20
    assert scaled["volume"] == int(round(20 * adj["volume"]))


def test_macro_gate_off_passes(monkeypatch) -> None:
    monkeypatch.setenv("MACRO_FLOW_GATE_ENABLED", "false")
    r = evaluate_macro_flow_gate(side="buy")
    assert r.approved is True


def test_macro_gate_blocks_extreme_greed(monkeypatch) -> None:
    monkeypatch.setenv("MACRO_FLOW_GATE_ENABLED", "true")

    class FakeFG:
        fear_greed_index = 90

    monkeypatch.setattr(
        "core.sentiment.sentiment_analyzer.analyze_sentiment",
        lambda: FakeFG(),
    )
    # patch at import site inside function
    import core.sentiment.sentiment_analyzer as sa

    monkeypatch.setattr(sa, "analyze_sentiment", lambda: FakeFG())

    r = evaluate_macro_flow_gate(side="buy")
    assert r.approved is False


def test_multi_tier_defaults_30_percent(monkeypatch) -> None:
    monkeypatch.setattr(
        "execution.smart_exits.get_settings",
        lambda: SimpleNamespace(
            breakeven_enabled=True,
            trailing_stop_enabled=True,
            institutional_v13={
                "multi_tier_tp_enabled": True,
                "multi_tier_tp1_pct": 0.30,
                "multi_tier_tp2_pct": 0.40,
            },
        ),
    )
    pos = Position(
        symbol="ADA/USDT",
        side=OrderSide.BUY,
        amount=100.0,
        entry_price=1.0,
        stop_loss=0.97,
        take_profit=1.09,
    )
    action = evaluate_multi_tier_tp(pos, 1.03)
    assert action.partial_exit_amount == 30.0
    assert action.mark_breakeven is True
