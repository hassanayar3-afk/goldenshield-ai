from terminal.elite_gate import EliteTier, evaluate_elite_gate, evaluate_elite_for_entry
from terminal.scoring import classify_band, confidence_percent, risk_pct_for_confidence


def test_confidence_85():
    assert confidence_percent(8.5) == 85.0


def test_elite_gate_85_pass():
    d = evaluate_elite_gate(8.5)
    assert d.approved
    assert d.tier in {EliteTier.ELITE_BORDER, EliteTier.STRONG_ELITE}


def test_auto_requires_90():
    d = evaluate_elite_for_entry(8.5, for_auto_open=True)
    assert not d.approved


def test_risk_bands():
    assert risk_pct_for_confidence(9.5) == 0.02
    assert risk_pct_for_confidence(8.5) == 0.015
    assert classify_band(6.0).value == "rejected"
