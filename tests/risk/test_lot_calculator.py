from risk.lot_calculator import LotCalculator


def test_lot_calculator_from_100_balance():
    calc = LotCalculator(100.0)
    amount, sl, tp = calc.calculate(50.0, sl_pct=0.03)

    assert amount > 0
    assert sl == 48.5
    assert tp == 54.5
    assert calc.is_rr_acceptable(50.0, sl, tp)


def test_lot_calculator_rejects_below_min_balance():
    calc = LotCalculator(50.0)
    amount, sl, tp = calc.calculate(100.0)
    assert amount == 0.0


def test_lot_calculator_zero_price():
    calc = LotCalculator(100.0)
    amount, sl, tp = calc.calculate(0.0)
    assert amount == 0.0
    assert sl == 0.0
    assert tp == 0.0


def test_lot_risk_is_one_percent():
    calc = LotCalculator(1000.0)
    amount, sl, tp = calc.calculate(100.0, sl_pct=0.05)
    # مخاطرة 1% = 10 USDT / خسارة 5 per unit = 2 units
    assert amount == 2.0
