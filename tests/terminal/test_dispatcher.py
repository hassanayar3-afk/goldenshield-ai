from dataclasses import dataclass

from terminal.dispatcher import DispatchStage, evaluate_dispatch, evaluate_min_notional_shield


@dataclass(frozen=True)
class _Proposal:
    commander: str
    symbol: str
    side: str
    price: float
    score: float
    signal: str
    reasons: tuple[str, ...]
    passed: bool


def test_elite_rejects_low_score():
    prop = _Proposal("gold_flash", "BTC/USDT", "buy", 50000.0, 7.0, "BUY SIGNAL", (), True)
    d = evaluate_dispatch(prop, open_positions=[], balance=5000.0)
    assert not d.approved
    assert d.stage == DispatchStage.ELITE_GATE


def test_min_notional_shield():
    ok, reason, amt = evaluate_min_notional_shield(
        price=100.0,
        balance=10.0,
        risk_pct=0.01,
    )
    assert isinstance(reason, str)
    assert amt >= 0.0
