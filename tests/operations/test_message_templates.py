from operations.alert_dispatcher import AlertLevel
from operations.message_templates import (
    escape,
    format_alert_message,
    format_cycle_signals_message,
    format_daily_report_plain,
    format_help_message,
    format_signal_message,
    format_startup_message,
    format_status_message,
    format_trade_close_message,
    strip_html,
)


def test_escape_html_special_chars():
    assert escape("A & B <C>") == "A &amp; B &lt;C&gt;"


def test_startup_message_has_brand_and_mode():
    text = format_startup_message(
        env="dev",
        mode="PAPER",
        pairs=["BTC/USDT", "ETH/USDT"],
        db_path="storage/db/test.db",
    )
    assert "GoldenShield AI" in text
    assert "PAPER" in text
    assert "BTC/USDT" in text
    assert "━━━━━━━━━━━━━━━" in text


def test_alert_message_removes_technical_prefix():
    text = format_alert_message(AlertLevel.INFO.value, "بدء التشغيل", "تفاصيل")
    assert "[INFO]" not in text
    assert "بدء التشغيل" in text
    assert "تفاصيل" in text


def test_opened_trades_digest_keeps_live_tag():
    from operations.message_templates import format_opened_trades_digest

    text = format_opened_trades_digest(
        [
            {
                "symbol": "BCH/USDT",
                "side": "بيع",
                "amount": 1.48,
                "entry": 225.38,
                "sl": 233.19,
                "tp": 212.82,
                "mode": "LIVE",
                "score": 8,
            },
            {
                "symbol": "FOREX/AUDUSD",
                "side": "شراء",
                "amount": 481.4,
                "entry": 0.70,
                "sl": 0.68,
                "tp": 0.74,
                "mode": "LIVE",
                "score": 9,
            },
        ]
    )
    assert "صفقات فُتحت" in text
    assert "LIVE" in text
    assert "مباشر" in text
    assert "BCH" in text
    assert "AUDUSD" in text
    assert "🛑" in text
    assert "💎" in text
    assert "<pre>" not in text
    assert text.index("BCH") < text.index("AUDUSD")


def test_qualified_signals_digest_weak_to_strong():
    from operations.dashboard_templates import format_qualified_signals_digest

    text = format_qualified_signals_digest(
        [
            {
                "symbol": "BTC/USDT",
                "price": 100.0,
                "score": 10,
                "signal": "BUY SIGNAL",
                "passed": True,
            },
            {
                "symbol": "XAU/USD",
                "price": 2300.0,
                "score": 8,
                "signal": "SELL SIGNAL",
                "passed": True,
            },
        ]
    )
    assert "صفقات جاهزة للدخول" in text
    assert text.index("XAU") < text.index("BTC")
    assert "💪" in text
    assert "<pre>" not in text


def test_cycle_signals_message_lists_all_pairs():
    text = format_cycle_signals_message(
        [
            {"symbol": "BTC/USDT", "price": 63568.97, "score": 5, "signal": "WAIT"},
            {"symbol": "ETH/USDT", "price": 1811.32, "score": 1, "signal": "WAIT"},
        ]
    )
    assert "تحديث السوق" in text
    assert "BTC" in text
    assert "انتظر" in text
    assert "⏳" in text


def test_signal_buy_message_structure():
    text = format_signal_message(
        symbol="BTC/USDT",
        price=63568.97,
        score=8,
        signal="BUY SIGNAL",
        kind="buy",
    )
    assert "فرصة شراء" in text
    assert "BTC" in text
    assert "63,568.97" in text


def test_trade_close_message_shows_pnl():
    text = format_trade_close_message("ETH/USDT", 12.5, "TP")
    assert "إغلاق صفقة" in text
    assert "+12.50" in text
    assert "TP" in text


def test_status_message_contains_balance():
    text = format_status_message(
        bot_username="GoldenShield_2026_bot",
        paused=False,
        balance=10000.0,
        daily_pnl="+0.00%",
        open_count=0,
        kill_switch="غير مفعّل",
    )
    assert "/status" not in text
    assert "10,000.00" in text
    assert "نشط" in text


def test_help_message_lists_commands():
    text = format_help_message()
    assert "/start" in text
    assert "/market" in text
    assert "/positions" in text
    assert "/panic" in text


def test_daily_report_plain_no_html():
    class _State:
        current_balance = 10000.0
        daily_pnl_pct = 1.25
        daily_trades = 2
        consecutive_losses = 0
        kill_switch_active = False
        daily_profit = 150.0
        daily_loss = 25.0

        @property
        def daily_net_pnl(self):
            return self.daily_profit - self.daily_loss

    class _Risk:
        state = _State()

    class _Positions:
        def count(self):
            return 1

    class _Executor:
        position_manager = _Positions()

    text = format_daily_report_plain(risk=_Risk(), executor=_Executor())
    assert "<b>" not in text
    assert "تقرير GoldenShield" in text
    assert "ربح اليوم" in text
    assert "خسارة اليوم" in text
    assert "150.00" in text
    assert "25.00" in text


def test_risk_state_tracks_daily_profit_and_loss():
    from risk.state import RiskState

    state = RiskState(session_start_balance=10000.0, current_balance=10000.0)
    state.record_trade(50.0)
    state.record_trade(-20.0)
    state.record_trade(10.0)
    assert state.daily_profit == 60.0
    assert state.daily_loss == 20.0
    assert state.daily_net_pnl == 40.0
    assert state.daily_trades == 3


def test_strip_html():
    assert strip_html("<b>test</b>") == "test"
