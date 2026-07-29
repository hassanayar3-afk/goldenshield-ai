from risk.kill_switch import check_kill_switch


def test_kill_switch_triggers_at_minus_3_percent():
    result = check_kill_switch(-3.0)
    assert result.triggered is True
    assert "-3" in result.reason


def test_kill_switch_not_triggered_above_threshold():
    result = check_kill_switch(-2.5)
    assert result.triggered is False


def test_kill_switch_triggers_below_threshold():
    result = check_kill_switch(-5.0)
    assert result.triggered is True
