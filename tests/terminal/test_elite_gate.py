from terminal.elite_gate import evaluate_elite_gate
from terminal.scoring import confidence_percent, risk_pct_for_confidence


def test_confidence_linear():
    assert confidence_percent(8.5) == 85.0
    assert confidence_percent(9) == 90.0


def test_elite_gate_85():
    ok = evaluate_elite_gate(8.5)
    assert ok.approved
    bad = evaluate_elite_gate(8.4)
    assert not bad.approved


def test_risk_sizing_bands():
    assert risk_pct_for_confidence(10) == 0.02
    assert risk_pct_for_confidence(8.5) == 0.015
    assert risk_pct_for_confidence(7.5) == 0.01
    assert risk_pct_for_confidence(6) == 0.0
