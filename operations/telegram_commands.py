"""أوامر Telegram — لوحة تداول تفاعلية."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING

import requests

from config.settings import get_settings
from operations.bot_admin import can_control_bot
from operations.message_templates import format_help_message
from operations.shutdown_guard import is_user_stopped, should_block_signals
from operations.telegram_admin import handle_admin_command
from operations.telegram_bot import TelegramBot
from operations.telegram_dashboard import TelegramDashboard

if TYPE_CHECKING:
    from audit.audit_trail import AuditTrail
    from execution.trade_executor import TradeExecutor
    from operations.panic_button import PanicButton
    from operations.runtime_state import OperationsRuntime
    from risk.risk_orchestrator import RiskOrchestrator

logger = logging.getLogger(__name__)


class TelegramCommandHandler:
    def __init__(
        self,
        *,
        runtime: OperationsRuntime,
        executor: TradeExecutor,
        risk: RiskOrchestrator,
        panic: PanicButton,
        audit: AuditTrail | None = None,
        telegram: TelegramBot | None = None,
        price_fetcher=None,
    ) -> None:
        self.runtime = runtime
        self.executor = executor
        self.risk = risk
        self.panic = panic
        self.audit = audit
        self.telegram = telegram or TelegramBot()
        self.dashboard = TelegramDashboard(
            runtime=runtime,
            executor=executor,
            risk=risk,
            panic=panic,
            audit=audit,
            telegram=self.telegram,
            price_fetcher=price_fetcher,
        )
        self._price_fetcher = price_fetcher
        self._offset: int | None = None
        self._poll_lock = threading.Lock()
        self._poll_thread: threading.Thread | None = None
        self._stop_poll = threading.Event()
        self._last_signals_fingerprint: str | None = None
        settings = get_settings()
        self._enabled = bool(settings.telegram_token and settings.telegram_chat_id)
        self._updates_url = (
            f"https://api.telegram.org/bot{settings.telegram_token}/getUpdates"
            if settings.telegram_token
            else None
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def update_market_snapshot(
        self,
        entries: list[dict],
        prices: dict[str, float] | None = None,
        *,
        reasons: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.dashboard.update_market(entries, prices, reasons=reasons)

    def send_trade_opportunity(
        self,
        symbol: str,
        entry: dict,
        *,
        reasons: tuple[str, ...] = (),
    ) -> None:
        if should_block_signals() or self.runtime.user_stopped:
            return
        view = self.dashboard.build_trade_alert(symbol, entry, reasons)
        self.telegram.send_message(view.text, reply_markup=view.keyboard)

    def send_qualified_signals_list(self, entries: list[dict]) -> bool:
        """رسالة واحدة بالصفقات الجاهزة (تلقائي/يدوي) — بدون WAIT."""
        from core.constants import score_to_percent
        from operations.dashboard_templates import format_qualified_signals_digest
        from operations.signal_filter import annotate_entry_actions
        from operations.telegram_keyboards import market_keyboard

        if should_block_signals() or self.runtime.user_stopped or not self.enabled:
            return False

        open_count = self.executor.position_manager.count()
        ordered = annotate_entry_actions(entries, open_positions=open_count)
        if not ordered:
            return False

        fingerprint = "|".join(
            f"{e.get('symbol')}:{e.get('signal')}:{score_to_percent(int(e.get('score', 0)))}"
            f":{e.get('entry_action', '')}"
            for e in ordered
        )
        if fingerprint == self._last_signals_fingerprint:
            return False

        text = format_qualified_signals_digest(ordered)
        keyboard = market_keyboard(
            [e["symbol"] for e in ordered],
            entries=ordered,
        )
        ok = self.telegram.send_message(text, reply_markup=keyboard)
        if ok:
            self._last_signals_fingerprint = fingerprint
        return bool(ok)

    def send_watchlist_digest(self) -> None:
        """لا نرسل قائمة انتظار — نفس قائمة الصفقات الجاهزة فقط."""
        return

    def handle(self, command: str) -> tuple[str, dict | None]:
        admin_reply = handle_admin_command(command)
        if admin_reply is not None:
            return admin_reply, self.dashboard.render_main().keyboard

        cmd = command.strip().lower().split()[0]

        if cmd in {"/start", "/menu", "/dashboard", "start", "menu", "dashboard"}:
            view = self.dashboard.render_main()
            return view.text, view.keyboard

        if cmd in {"/market", "market"}:
            view = self.dashboard.render_market()
            return view.text, view.keyboard

        if cmd in {"/positions", "positions"}:
            view = self.dashboard.render_positions()
            return view.text, view.keyboard

        if cmd in {"/pause", "pause"}:
            self.runtime.pause()
            view = self.dashboard.render_main()
            return view.text, view.keyboard

        if cmd in {"/resume", "resume"}:
            if self.runtime.user_stopped or is_user_stopped():
                return (
                    "⛔ البوت متوقف بقرارك. شغّل <b>00_START.bat</b> على السيرفر للعودة.",
                    self.dashboard.render_main().keyboard,
                )
            self.runtime.resume()
            view = self.dashboard.render_main()
            return view.text, view.keyboard

        if cmd in {"/panic", "panic"}:
            self.runtime.stop_permanently(reason="telegram_panic")
            symbols = list(self.executor.position_manager.open_symbols())
            prices = self._fetch_prices(symbols) if symbols else {}
            result = self.panic.trigger(prices, reason="أمر Telegram /panic")
            view = self.dashboard.render_main()
            return (
                f"{view.text}\n\n🚨 {result.message}\n\n"
                "⛔ <b>إيقاف كامل</b> — لن تُرسل إشارات ولن يُعاد التشغيل تلقائياً.",
                view.keyboard,
            )

        if cmd in {"/stop", "stop"}:
            self.runtime.stop_permanently(reason="telegram_stop")
            view = self.dashboard.render_main()
            return (
                f"{view.text}\n\n⛔ <b>تم الإيقاف الكامل</b> — لا إشارات ولا إعادة تشغيل تلقائي.",
                view.keyboard,
            )

        if cmd in {"/losses", "/losing", "losses", "losing"}:
            from operations.loss_trade_report import (
                format_losing_trades_digest,
                load_losing_trade_reports,
            )

            reports = load_losing_trade_reports(limit=20)
            return format_losing_trades_digest(reports, limit=10), self.dashboard.render_main().keyboard

        if cmd in {"/loss_detail", "loss_detail"}:
            from operations.loss_trade_report import (
                find_reports_for_symbol,
                format_losing_trade_report_telegram,
            )

            parts = command.strip().split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                return (
                    "استخدم: <b>/loss_detail BTC/USDT</b>",
                    self.dashboard.render_main().keyboard,
                )
            symbol = parts[1].strip().upper()
            matched = find_reports_for_symbol(symbol, limit=3)
            if not matched:
                return (
                    f"لا يوجد تقرير خسارة محفوظ لـ <code>{symbol}</code>.",
                    self.dashboard.render_main().keyboard,
                )
            texts = [format_losing_trade_report_telegram(row) for row in matched]
            return "\n\n────────\n\n".join(texts), self.dashboard.render_main().keyboard

        return format_help_message(), self.dashboard.render_main().keyboard

    def _process_callback(self, callback: dict) -> bool:
        callback_id = callback.get("id", "")
        data = str(callback.get("data", ""))
        message = callback.get("message") or {}
        message_id = message.get("message_id")
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        settings = get_settings()

        if chat_id != str(settings.telegram_chat_id) and not can_control_bot(chat_id):
            self.telegram.answer_callback_query(callback_id, "غير مصرح")
            return False

        try:
            # أزل ساعة التحميل فوراً — قبل أي عمل ثقيل
            self.telegram.answer_callback_query(callback_id)

            view = self.dashboard.handle_callback(data)
            ok = False
            if isinstance(message_id, int):
                ok = self.telegram.edit_message_text(
                    message_id,
                    view.text,
                    reply_markup=view.keyboard,
                    chat_id=chat_id or None,
                )
            if not ok:
                sent_id = self.telegram.send_message(
                    view.text,
                    reply_markup=view.keyboard,
                    chat_id=chat_id or None,
                )
                if data == "view:positions" and isinstance(sent_id, int):
                    self.dashboard.enable_live_positions(sent_id, chat_id or None)
            elif data == "view:positions" and isinstance(message_id, int):
                self.dashboard.enable_live_positions(message_id, chat_id or None)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("فشل معالجة زر Telegram (%s): %s", data, exc)
            try:
                self.telegram.answer_callback_query(
                    callback_id, "فشل التنفيذ — أعد المحاولة", show_alert=True
                )
            except Exception:
                pass
            try:
                self.telegram.send_message(
                    f"⚠️ فشل زر <code>{data}</code>: {exc}",
                    chat_id=chat_id or None,
                )
            except Exception:
                pass
            return False

    def poll_once(self, *, long_poll: bool = False) -> int:
        if not self._enabled or not self._updates_url:
            return 0

        # long poll في الخيط المخصص؛ القصير من main لا يتعارض
        if not self._poll_lock.acquire(blocking=not long_poll):
            return 0
        try:
            return self._poll_once_locked(long_poll=long_poll)
        finally:
            self._poll_lock.release()

    def _poll_once_locked(self, *, long_poll: bool) -> int:
        assert self._updates_url is not None
        timeout = 25 if long_poll else 0
        params: dict[str, int] = {"timeout": timeout}
        if self._offset is not None:
            params["offset"] = self._offset

        try:
            http_timeout = timeout + 10 if long_poll else 10
            response = requests.get(
                self._updates_url, params=params, timeout=http_timeout
            )
            if response.status_code != 200:
                return 0
            payload = response.json()
        except Exception as exc:
            logger.debug("فشل poll Telegram: %s", exc)
            return 0

        updates = payload.get("result", [])
        processed = 0
        settings = get_settings()

        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                self._offset = update_id + 1

            callback = update.get("callback_query")
            if callback:
                if self._process_callback(callback):
                    processed += 1
                continue

            message = update.get("message") or {}
            chat = message.get("chat") or {}
            chat_id = str(chat.get("id", ""))
            if chat_id != str(settings.telegram_chat_id) and not can_control_bot(chat_id):
                continue

            text = message.get("text", "")
            if not text.startswith("/"):
                continue

            reply, keyboard = self.handle(text)
            self.telegram.send_message(reply, reply_markup=keyboard)
            processed += 1

        return processed

    def start_background_polling(self) -> None:
        """خيط مستقل بـ long-poll — لا يتأخر بسبب دورة التحليل."""
        if not self._enabled or self._poll_thread is not None:
            return

        self._stop_poll.clear()

        def _run() -> None:
            logger.info("Telegram long-poll thread started")
            while not self._stop_poll.is_set():
                try:
                    # عند البث الحي: مهلة أقصر لتحديث الأسعار بسرعة
                    live = self.dashboard.live_positions_active
                    self.poll_once(long_poll=not live)
                    self.dashboard.tick_live_positions()
                    if live:
                        time.sleep(1.0)
                except Exception as exc:
                    logger.warning("خطأ في حلقة Telegram: %s", exc)
                    time.sleep(1.0)

        self._poll_thread = threading.Thread(
            target=_run,
            name="telegram-poll",
            daemon=True,
        )
        self._poll_thread.start()

    async def poll_loop(self, interval_seconds: float = 0.0) -> None:
        """توافق خلفي — يفضّل start_background_polling."""
        self.start_background_polling()
        while not self._stop_poll.is_set():
            await asyncio.sleep(max(interval_seconds, 5.0))

    def _fetch_prices(self, symbols: list[str]) -> dict[str, float]:
        if self._price_fetcher is None:
            return {}
        return self._price_fetcher(symbols)
