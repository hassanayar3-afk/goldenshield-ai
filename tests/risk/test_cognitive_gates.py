"""اختبارات بوابة عمق السوق والأوزان والماكرو والتخارج."""

from __future__ import annotations

from pathlib import Path

from database.connection import init_database
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

    import core.sentiment.sentiment_analyzer as sa

    monkeypatch.setattr(sa, "analyze_sentiment", lambda: FakeFG())

    r = evaluate_macro_flow_gate(side="buy")
    assert r.approved is False
