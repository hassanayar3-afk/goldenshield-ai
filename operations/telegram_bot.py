"""بوت Telegram — إرسال رسائل HTML مع أزرار تفاعلية."""

from __future__ import annotations

import json
import logging
import time
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
        # حماية من 429: إيقاف التعديلات العدوانية حتى ينتهي الانتظار
        self._flood_until_mono: float = 0.0
        self.last_edit_reason: str = ""

    @property
    def configured(self) -> bool:
        return bool(self._api_base and self.chat_id)

    def flood_active(self) -> bool:
        return time.monotonic() < float(self._flood_until_mono or 0.0)

    def _mark_flood(self, retry_after: float) -> None:
        # سقف ساعة في الذاكرة التشغيلية حتى لا تبقى الأزرار ميتة لأيام بالخطأ
        wait = max(1.0, min(float(retry_after or 30.0), 3600.0))
        self._flood_until_mono = time.monotonic() + wait
        logger.warning("Telegram flood wait ~%.0fs — pausing live edits", wait)

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self._api_base:
            return None
        # أثناء الفيض: لا نرسل editMessageText أبداً (سبب موت الأزرار)
        if self.flood_active() and method == "editMessageText":
            return None
        try:
            response = requests.post(
                f"{self._api_base}/{method}",
                json=payload,
                timeout=15,
            )
            if response.status_code == 429:
                retry_after = 30.0
                try:
                    body = response.json()
                    retry_after = float(
                        (body.get("parameters") or {}).get("retry_after") or 30
                    )
                except Exception:
                    pass
                self._mark_flood(retry_after)
                logger.warning(
                    "Telegram %s failed (429): retry_after=%.0f",
                    method,
                    retry_after,
                )
                return None
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
                desc = str(data.get("description", ""))
                if "Too Many Requests" in desc or "retry after" in desc.lower():
                    try:
                        retry_after = float(
                            (data.get("parameters") or {}).get("retry_after") or 30
                        )
                    except Exception:
                        retry_after = 30.0
                    self._mark_flood(retry_after)
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

    def _classify_edit_error(self, description: str) -> str:
        desc = (description or "").lower()
        if "message is not modified" in desc:
            return "unchanged"
        if "message to edit not found" in desc or "message_id_invalid" in desc:
            return "not_found"
        if "message can't be edited" in desc or "too old" in desc:
            return "too_old"
        if "too many requests" in desc or "retry after" in desc:
            return "flood"
        return "error"

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
            self.last_edit_reason = "not_configured"
            return False
        if self.flood_active():
            self.last_edit_reason = "flood"
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
        try:
            response = requests.post(
                f"{self._api_base}/editMessageText",
                json=payload,
                timeout=15,
            )
            if response.status_code == 429:
                retry_after = 30.0
                try:
                    body = response.json()
                    retry_after = float(
                        (body.get("parameters") or {}).get("retry_after") or 30
                    )
                except Exception:
                    pass
                self._mark_flood(retry_after)
                self.last_edit_reason = "flood"
                return False
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.last_edit_reason = "ok"
                    return True
                desc = str(data.get("description", ""))
                self.last_edit_reason = self._classify_edit_error(desc)
                if self.last_edit_reason == "unchanged":
                    return True
                logger.warning("Telegram editMessageText error: %s", data)
                return False
            desc = ""
            try:
                desc = str((response.json() or {}).get("description", ""))
            except Exception:
                desc = response.text[:300]
            self.last_edit_reason = self._classify_edit_error(desc)
            if self.last_edit_reason == "unchanged":
                return True
            logger.warning(
                "Telegram editMessageText failed (%s): %s",
                response.status_code,
                desc or response.text[:300],
            )
            return False
        except Exception as exc:
            self.last_edit_reason = "error"
            logger.warning("Telegram editMessageText exception: %s", exc)
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
