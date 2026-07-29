from execution.sl_tp_calculator import calculate_sl_tp


def test_sl_tp_buy_side_default_rr():
    sl, tp = calculate_sl_tp(100.0, sl_pct=0.03, rr_ratio=2.0)
    assert sl == 97.0
    assert tp == 106.0


def test_sl_tp_invalid_price():
    sl, tp = calculate_sl_tp(0.0)
    assert sl == 0.0
    assert tp == 0.0
