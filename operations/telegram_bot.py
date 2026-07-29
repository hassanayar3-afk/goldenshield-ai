"""بوت Telegram — إرسال رسائل HTML مع أزرار تفاعلية."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from config.settings import get_settings

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        settings = get_settings()
        self.token = token or settings.telegram_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self._api_base = f"https://api.telegram.org/bot{self.token}" if self.token else None

    @property
    def configured(self) -> bool:
        return bool(self._api_base and self.chat_id)

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self._api_base:
            return None
        try:
            response = requests.post(
                f"{self._api_base}/{method}",
                json=payload,
                timeout=15,
            )
            if response.status_code != 200:
                logger.warning(
                    "Telegram %s failed (%s): %s",
                    method,
                    response.status_code,
                    response.text[:300],
                )
                return None
            data = response.json()
            if not data.get("ok"):
                logger.warning("Telegram %s error: %s", method, data)
                return None
            return data.get("result")
        except Exception as exc:
            logger.warning("Telegram %s exception: %s", method, exc)
            return None

    def send_message(
        self,
        text: str,
        *,
        parse_mode: str = "HTML",
        reply_markup: dict | None = None,
        disable_preview: bool = True,
        chat_id: str | None = None,
    ) -> int | None:
        if not self.configured and not (self._api_base and (chat_id or self.chat_id)):
            logger.debug("Telegram غير مُعدّ — تخطي الإرسال")
            return None
        target = chat_id or self.chat_id
        if not self._api_base or not target:
            return None

        # حد تيليجرام
        if len(text) > 4000:
            text = text[:3990] + "…"

        payload: dict[str, Any] = {
            "chat_id": target,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        result = self._call("sendMessage", payload)
        if isinstance(result, dict):
            return result.get("message_id")
        return None

    def edit_message_text(
        self,
        message_id: int,
        text: str,
        *,
        parse_mode: str = "HTML",
        reply_markup: dict | None = None,
        chat_id: str | None = None,
    ) -> bool:
        target = chat_id or self.chat_id
        if not self._api_base or not target:
            return False

        if len(text) > 4000:
            text = text[:3990] + "…"

        payload: dict[str, Any] = {
            "chat_id": target,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        result = self._call("editMessageText", payload)
        if result is not None:
            return True
        # "message is not modified" يُعامل كنجاح عملي
        return False

    def answer_callback_query(
        self,
        callback_id: str,
        text: str | None = None,
        *,
        show_alert: bool = False,
    ) -> bool:
        payload: dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text[:200]
        if show_alert:
            payload["show_alert"] = True
        return self._call("answerCallbackQuery", payload) is not None

    def reply_markup_json(self, markup: dict) -> str:
        return json.dumps(markup, ensure_ascii=False)
