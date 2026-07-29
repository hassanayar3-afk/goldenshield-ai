from operations.dashboard_templates import (
    format_entry_block_reason,
    format_trade_setup_card,
    risk_grade_from_score,
)
from operations.telegram_keyboards import (
    decode_symbol,
    encode_symbol,
    main_menu_keyboard,
    position_trade_keyboard,
    trade_entry_keyboard,
)
from risk.risk_orchestrator import RiskApproval


def test_encode_decode_symbol():
    assert encode_symbol("BTC/USDT") == "BTCUSDT"
    assert decode_symbol("BTCUSDT") == "BTC/USDT"


def test_risk_grade_premium():
    grade = risk_grade_from_score(9, signal="BUY SIGNAL")
    assert grade.icon == "🟢"
    assert "جاهزة" in grade.label


def test_risk_grade_weak():
    grade = risk_grade_from_score(2, signal="WAIT")
    assert grade.icon == "🔴"


def test_entry_block_reason_wait_signal():
    reason = format_entry_block_reason(
        signal="WAIT",
        score=5,
        premium=False,
        paused=False,
        has_position=False,
        approval_approved=True,
    )
    assert "انتظر" in reason


def test_entry_block_reason_low_score():
    reason = format_entry_block_reason(
        signal="BUY SIGNAL",
        score=5,
        premium=False,
        paused=False,
        has_position=False,
        approval_approved=True,
    )
    assert "75" in reason


def test_trade_setup_card_shows_why_no_entry():
    text = format_trade_setup_card(
        symbol="BTC/USDT",
        price=63500.0,
        score=5,
        signal="WAIT",
        can_enter=False,
        entry_block_reason="السوق يقول «انتظر» — ليس وقت شراء الآن.",
    )
    assert "انتظر" in text
    assert "ليس وقت شراء" in text


def test_trade_setup_card_shows_sl_tp_and_lot():
    approval = RiskApproval(
        approved=True,
        reason="test",
        amount=0.015,
        stop_loss=61500.0,
        take_profit=67000.0,
    )
    text = format_trade_setup_card(
        symbol="BTC/USDT",
        price=63500.0,
        score=9,
        signal="BUY SIGNAL",
        approval=approval,
        reasons=("محاذاة إطارات", "حجم قوي"),
        can_enter=True,
        balance=10000.0,
    )
    assert "قوة الصفقة" in text
    assert "تفاصيل الصفقة" in text
    assert "Entry" in text
    assert "SL" in text
    assert "TP" in text
    assert "نسبة الهدف" in text
    assert "$" in text


def test_trade_setup_shows_dollar_profit_even_when_waiting():
    text = format_trade_setup_card(
        symbol="BTC/USDT",
        price=63500.0,
        score=5,
        signal="WAIT",
        can_enter=False,
        balance=10000.0,
        entry_block_reason="السوق يقول «انتظر»",
    )
    assert "نسبة الهدف" in text
    assert "الخطورة" in text
    assert "$" in text
    assert "│" in text


def test_main_menu_keyboard_simple():
    kb = main_menu_keyboard(paused=False)
    labels = [btn["text"] for row in kb["inline_keyboard"] for btn in row]
    assert "📡 الإشارات" in labels
    assert "📂 مراكزي" in labels
    assert "📋 التقرير" in labels
    assert "🚨 طوارئ — إغلاق الكل" in labels


def test_main_menu_keyboard_resume_when_paused():
    kb = main_menu_keyboard(paused=True)
    labels = [btn["text"] for row in kb["inline_keyboard"] for btn in row]
    assert "▶️ تشغيل" in labels


def test_trade_entry_keyboard_minimal():
    kb = trade_entry_keyboard("BTC/USDT", can_enter=True)
    labels = [btn["text"] for row in kb["inline_keyboard"] for btn in row]
    assert "✅ دخول الصفقة الآن" in labels
    assert not any(label == "SL" for label in labels)


def test_position_keyboard_minimal():
    kb = position_trade_keyboard("BTC/USDT")
    labels = [btn["text"] for row in kb["inline_keyboard"] for btn in row]
    assert "❌ إغلاق الصفقة" in labels
    assert "🔄 تحديث" in labels
