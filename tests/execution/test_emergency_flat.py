from execution.emergency_flat import emergency_flat
from execution.models.order import Order, OrderSide, OrderStatus, OrderType
from execution.models.trade import Position
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager
from execution.trade_executor import TradeExecutor
from risk.risk_orchestrator import RiskOrchestrator


def test_emergency_flat_closes_all_positions():
    order_manager = OrderManager()
    position_manager = PositionManager()
    position_manager.add(
        Position(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=100.0,
            amount=0.5,
            stop_loss=97.0,
            take_profit=106.0,
        )
    )
    position_manager.add(
        Position(
            symbol="ETH/USDT",
            side=OrderSide.BUY,
            entry_price=50.0,
            amount=1.0,
            stop_loss=48.0,
            take_profit=54.0,
        )
    )

    results = emergency_flat(
        order_manager,
        position_manager,
        prices={"BTC/USDT": 101.0, "ETH/USDT": 51.0},
    )

    assert sorted(r.symbol for r in results) == ["BTC/USDT", "ETH/USDT"]
    assert position_manager.count() == 0
    assert len(order_manager.orders) == 2
    assert results[0].pnl != 0 or results[1].pnl != 0


def test_emergency_close_all_records_risk_pnl():
    risk = RiskOrchestrator()
    risk.initialize(10000.0)
    executor = TradeExecutor(risk_orchestrator=risk)
    executor.position_manager.add(
        Position(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=100.0,
            amount=1.0,
            stop_loss=97.0,
            take_profit=106.0,
        )
    )

    closed = executor.emergency_close_all({"BTC/USDT": 105.0})

    assert closed == ["BTC/USDT"]
    assert risk.state is not None
    assert risk.state.daily_trades == 1
    assert risk.state.current_balance == 10005.0


def test_modify_order_updates_amount_and_price():
    order_manager = OrderManager()
    pending = Order(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        amount=0.2,
        order_type=OrderType.LIMIT,
        price=99.0,
        status=OrderStatus.OPEN,
    )
    order_manager._orders[pending.id] = pending

    updated = order_manager.modify_order(pending.id, amount=0.3, price=98.5)
    assert updated.amount == 0.3
    assert updated.price == 98.5


def test_modify_order_rejects_filled_order():
    order_manager = OrderManager()
    filled = order_manager.create_market_order(
        "BTC/USDT",
        OrderSide.BUY,
        0.1,
        reference_price=100.0,
        stop_loss=97.0,
        take_profit=109.0,
    )
    try:
        order_manager.modify_order(filled.id, amount=0.2)
        raise AssertionError("يجب رفض تعديل أمر منفّذ")
    except Exception as exc:
        assert "منفّذ" in str(exc)
