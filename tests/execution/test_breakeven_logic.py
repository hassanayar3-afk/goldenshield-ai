from execution.breakeven_logic import evaluate_breakeven
from execution.models.order import OrderSide
from execution.models.trade import Position


def _long_position() -> Position:
    return Position(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=100.0,
        amount=1.0,
        stop_loss=97.0,
        take_profit=106.0,
    )


def test_breakeven_triggers_at_one_to_one():
    position = _long_position()
    action = evaluate_breakeven(position, current_price=103.0)

    assert action.move_sl_to_breakeven is True
    assert action.new_stop_loss == 100.0
    assert action.partial_exit_amount == 0.5
    assert action.mark_partial_exit is True


def test_breakeven_not_triggered_before_one_to_one():
    position = _long_position()
    action = evaluate_breakeven(position, current_price=102.0)

    assert action.move_sl_to_breakeven is False
    assert action.partial_exit_amount == 0.0


def test_breakeven_skips_when_already_applied():
    position = _long_position()
    position.breakeven_applied = True
    position.partial_exit_done = True

    action = evaluate_breakeven(position, current_price=105.0)

    assert action.move_sl_to_breakeven is False
    assert action.partial_exit_amount == 0.0
