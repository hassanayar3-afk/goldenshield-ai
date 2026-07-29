from core.constants import (
    is_auto_entry_allowed,
    is_golden_opportunity,
    score_to_percent,
)


def test_score_map() -> None:
    assert score_to_percent(8) == 75
    assert score_to_percent(9) == 90
    assert score_to_percent(10) == 100


def test_score_75_is_manual_only() -> None:
    ok, reason = is_auto_entry_allowed(8, 0)
    assert ok is False
    assert "يدوي" in reason


def test_score_90_is_manual_not_guaranteed() -> None:
    """90/100 غير مضمون — يدوي فقط وفق عتبة 95."""
    ok, reason = is_auto_entry_allowed(9, 0)
    assert ok is False
    assert "يدوي" in reason
    assert not is_golden_opportunity(9)


def test_score_100_is_auto_golden() -> None:
    assert is_golden_opportunity(10) is True
    ok, reason = is_auto_entry_allowed(10, 0)
    assert ok is True
    assert "ذهبية" in reason or "تلقائي" in reason


def test_soft_auto_when_threshold_90() -> None:
    """توافق خلفي: إن خُفّضت العتبة إلى 90 يُسمح بالدرجة 9."""
    ok, reason = is_auto_entry_allowed(9, 0, soft_min=90)
    assert ok is True
    assert "تلقائي" in reason


def test_soft_slot_limit() -> None:
    ok, reason = is_auto_entry_allowed(9, 3, soft_min=90)
    assert ok is False
    assert "ناعمة" in reason or "يدوي" in reason


def test_strong_slot_limit() -> None:
    ok, _ = is_auto_entry_allowed(10, 11)
    assert ok is True
    ok, reason = is_auto_entry_allowed(10, 12)
    assert ok is False
    assert "12" in reason


def test_below_75_no_auto() -> None:
    ok, reason = is_auto_entry_allowed(7, 0)
    assert ok is False
    assert "تلقائي" in reason or "يدوي" in reason or "دون" in reason
