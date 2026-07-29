from datetime import date

from database.connection import init_database
from database.repositories.config_repo import ConfigRepository
from database.repositories.risk_state_repo import load_risk_state, save_risk_state
from database.repositories.trade_repo import TradeRepository, TradeRow
from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.trade_executor import TradeExecutor
from risk.state import RiskState


def test_settings_import_no_circular():
    from config.settings import load_settings

    settings = load_settings(reload=True)
    assert settings.env in {"dev", "staging", "production"}


def test_health_check_settings_path():
    from deployment import health_check

    # الاستيراد نفسه كان ينهار بدورة الاستيراد — يكفي أن تتحمل الوحدة التحميل
    assert callable(health_check.main)


def test_risk_state_roundtrip(tmp_path):
    db = init_database(str(tmp_path / "t.db"))
    repo = ConfigRepository(db)
    state = RiskState(
        session_start_balance=10000.0,
        current_balance=9800.0,
        consecutive_losses=2,
        kill_switch_active=True,
        daily_trades=3,
    )
    save_risk_state(repo, state, date.today())
    loaded, day = load_risk_state(repo)
    assert loaded is not None
    assert loaded.current_balance == 9800.0
    assert loaded.kill_switch_active is True
    assert loaded.consecutive_losses == 2
    assert day == date.today()


def test_restore_open_positions(tmp_path):
    db = init_database(str(tmp_path / "t.db"))
    trade_repo = TradeRepository(db)
    trade_repo.save_trade(
        TradeRow(
            id="pos-test1",
            symbol="BTC/USDT",
            side="buy",
            entry_price=60000.0,
            amount=0.01,
            status="open",
            opened_at="2026-07-14T00:00:00+00:00",
            stop_loss=58000.0,
            take_profit=64000.0,
            is_paper=True,
        )
    )
    executor = TradeExecutor(trade_repository=trade_repo)
    assert executor.restore_open_positions() == 1
    pos = executor.position_manager.get("BTC/USDT")
    assert pos is not None
    assert pos.id == "pos-test1"
    assert pos.stop_loss == 58000.0
    assert pos.side == OrderSide.BUY
