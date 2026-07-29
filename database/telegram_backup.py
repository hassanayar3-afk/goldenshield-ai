"""رفع النسخ الاحتياطية إلى قناة Telegram (الأرشيف)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramBackupResult:
    uploaded: bool
    message: str
    message_id: int | None = None


def _api_base(token: str) -> str:
    return f"https://api.telegram.org/bot{token}"


def format_backup_caption(
    *,
    filename: str,
    size_bytes: int,
    env: str,
    mode: str,
    extra: str = "",
) -> str:
    size_kb = size_bytes / 1024
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "🛡️ <b>النسخ الاحتياطي</b>",
        "━━━━━━━━━━━━━━━",
        "📦 <b>نسخة جديدة من GoldenShield</b>",
        "",
        f"📁 الملف: <code>{filename}</code>",
        f"📏 الحجم: <code>{size_kb:.1f} KB</code>",
        f"🌐 البيئة: <code>{env}</code>",
        f"⚙️ الوضع: <code>{mode}</code>",
        f"🕒 الوقت: <code>{stamp}</code>",
        "",
        "♻️ <b>للاستعادة:</b>",
        "1) حمّل الملف من هذه القناة",
        "2) ضعه مكان قاعدة البيانات المحلية",
        "3) أو شغّل: <code>scripts/restore_backup.py</code>",
    ]
    if extra:
        lines.extend(["", extra])
    return "\n".join(lines)


def upload_backup_to_telegram(
    backup_path: str,
    *,
    channel_id: str | None = None,
    caption_extra: str = "",
) -> TelegramBackupResult:
    """إرسال ملف النسخة الاحتياطية إلى قناة الأرشيف."""
    settings = get_settings()
    token = settings.telegram_token
    chat = (
        channel_id
        or settings.telegram_backup_channel_id
        or settings.telegram_chat_id
    )

    if not token:
        return TelegramBackupResult(False, "TELEGRAM_TOKEN غير مُعدّ")
    if not chat:
        return TelegramBackupResult(
            False,
            "TELEGRAM_BACKUP_CHANNEL_ID / TELEGRAM_CHAT_ID غير مُعدّ — راجع docs/TELEGRAM_BACKUP_CHANNEL.md",
        )

    path = Path(backup_path)
    if not path.exists():
        return TelegramBackupResult(False, f"الملف غير موجود: {backup_path}")

    caption = format_backup_caption(
        filename=path.name,
        size_bytes=path.stat().st_size,
        env=settings.env,
        mode=settings.execution_mode,
        extra=caption_extra,
    )
    # Telegram caption max 1024
    if len(caption) > 1000:
        caption = caption[:997] + "..."

    try:
        with path.open("rb") as fh:
            response = requests.post(
                f"{_api_base(token)}/sendDocument",
                data={
                    "chat_id": chat,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                files={"document": (path.name, fh)},
                timeout=60,
            )
        data = response.json()
        if response.status_code != 200 or not data.get("ok"):
            detail = data.get("description") if isinstance(data, dict) else response.text[:200]
            logger.warning("Telegram backup upload failed: %s", detail)
            return TelegramBackupResult(False, f"فشل الرفع للقناة: {detail}")

        result = data.get("result") or {}
        message_id = result.get("message_id")
        return TelegramBackupResult(
            True,
            f"رُفعت النسخة إلى قناة الأرشيف: {path.name}",
            message_id=message_id if isinstance(message_id, int) else None,
        )
    except Exception as exc:
        logger.warning("Telegram backup exception: %s", exc)
        return TelegramBackupResult(False, f"خطأ الرفع: {exc}")


def send_vault_intro(*, channel_id: str | None = None) -> TelegramBackupResult:
    """رسالة تصميم القناة (تُرسل مرة عند الإعداد)."""
    settings = get_settings()
    token = settings.telegram_token
    chat = channel_id or settings.telegram_backup_channel_id or settings.telegram_chat_id
    if not token or not chat:
        return TelegramBackupResult(False, "قناة/محادثة الأرشيف غير مُعدّة")

    text = (
        "🛡️ <b>النسخ الاحتياطي</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "<b>قناة أرشيف GoldenShield AI</b>\n\n"
        "📌 الغرض:\n"
        "• حفظ قاعدة البيانات يومياً\n"
        "• استرجاع المشروع بعد انقطاع أو جهاز جديد\n"
        "• سجل زمني للنسخ (التاريخ في اسم الملف)\n\n"
        "📦 ما يُحفظ هنا:\n"
        "• ملفات <code>*.db</code> من SQLite\n"
        "• تعليقات: البيئة · الوضع · الحجم · الوقت\n\n"
        "⚠️ هذه القناة خاصة — لا تشارك الرابط.\n"
        "البوت يكتب فقط؛ التحميل يدوي عند الحاجة للاستعادة."
    )
    try:
        response = requests.post(
            f"{_api_base(token)}/sendMessage",
            json={
                "chat_id": chat,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        data = response.json()
        if not data.get("ok"):
            return TelegramBackupResult(False, str(data.get("description", "فشل")))
        mid = (data.get("result") or {}).get("message_id")
        return TelegramBackupResult(True, "تم إرسال رسالة تصميم القناة", message_id=mid)
    except Exception as exc:
        return TelegramBackupResult(False, str(exc))
