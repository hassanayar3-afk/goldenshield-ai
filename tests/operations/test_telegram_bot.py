from operations.telegram_bot import TelegramBot


def test_classify_edit_error_unchanged():
    bot = TelegramBot(token=None, chat_id=None)
    assert bot._classify_edit_error("Bad Request: message is not modified") == "unchanged"


def test_classify_edit_error_not_found():
    bot = TelegramBot(token=None, chat_id=None)
    assert bot._classify_edit_error("Bad Request: message to edit not found") == "not_found"


def test_classify_edit_error_too_old():
    bot = TelegramBot(token=None, chat_id=None)
    assert bot._classify_edit_error("Bad Request: message can't be edited") == "too_old"
