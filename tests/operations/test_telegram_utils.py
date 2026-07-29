from operations.telegram_utils import validate_chat_id


def test_rejects_bot_id_as_chat_id():
    token = "8985362540:AAExampleToken"
    ok, detail = validate_chat_id(token, "8985362540")
    assert ok is False
    assert "Bot ID" in detail


def test_accepts_real_chat_id():
    token = "8985362540:AAExampleToken"
    ok, detail = validate_chat_id(token, "123456789")
    assert ok is True
    assert detail == "صالح"


def test_empty_chat_id_is_ok():
    ok, _ = validate_chat_id("8985362540:AAExample", None)
    assert ok is True
