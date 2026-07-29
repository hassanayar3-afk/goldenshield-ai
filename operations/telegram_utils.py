"""أدوات التحقق من إعدادات Telegram."""

from __future__ import annotations


def extract_bot_id(token: str | None) -> str | None:
    if not token or ":" not in token:
        return None
    return token.split(":", 1)[0].strip()


def validate_chat_id(token: str | None, chat_id: str | None) -> tuple[bool, str]:
    if not chat_id:
        return True, "غير مُعدّ — التنبيهات محلية فقط"

    bot_id = extract_bot_id(token)
    if bot_id and str(chat_id).strip() == bot_id:
        return (
            False,
            "CHAT_ID خاطئ: هذا Bot ID وليس محادثتك — أرسل /start للبوت ثم استخدم السكربت",
        )

    return True, "صالح"
