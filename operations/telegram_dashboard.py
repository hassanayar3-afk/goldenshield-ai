"""لوحة تحكم Telegram — حسب دستور GoldenShield.

قواعد المشروع الثابتة (لا تُعدَّل من اللوحة):
- مخاطرة 1% لكل صفقة (المرحلة 6)
- SL 3% / R:R 1:2 (المرحلة 5)
- Breakeven تلقائي عند 1:1 + خروج جزئي (المرحلة 5)
- دخول فقط بدرجة ≥75%
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from config.settings import get_settings
from core.analyzer import MarketAnalyzer
from operations.dashboard_templates import (
    format_action_result,
    format_entry_block_reason,
    format_live_signals_board,
    format_main_dashboard,
    format_position_card,
    format_positions_list,
    format_qualified_signals_digest,
    format_trade_setup_card,
    format_watchlist_digest,
)
from operations.daily_report import format_daily_report_telegram
from operations.message_templates import DIVIDER, escape
from operations.symbol_registry import get_symbol_registry
from operations.telegram_keyboards import (
    back_to_main_keyboard,
    decode_symbol,
    encode_symbol,
    main_menu_keyboard,
    market_keyboard,
    position_trade_keyboard,
    positions_list_keyboard,
    trade_entry_keyboard,
)

if TYPE_CHECKING:
    from audit.audit_trail import AuditTrail
    from execution.trade_executor import TradeExecutor
    from operations.panic_button import PanicButton
    from operations.runtime_state import OperationsRuntime
    from operations.telegram_bot import TelegramBot
    from risk.risk_orchestrator import RiskOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class DashboardView:
    text: str
    keyboard: dict


@dataclass
class MarketState:
    entries: dict[str, dict] = field(default_factory=dict)
    prices: dict[str, float] = field(default_factory=dict)
    reasons: dict[str, tuple[str, ...]] = field(default_factory=dict)


class TelegramDashboard:
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
        from operations.telegram_bot import TelegramBot as Bot

        self.runtime = runtime
        self.executor = executor
        self.risk = risk
        self.panic = panic
        self.audit = audit
        self.telegram = telegram or Bot()
        self._price_fetcher = price_fetcher
        self.market = MarketState()
        # بث حي لمراكز التيليجرام (تحديث تلقائي للرسالة)
        self._live_positions_msg_id: int | None = None
        self._live_positions_chat_id: str | None = None
        self._live_positions_enabled: bool = False
        self._live_positions_last_ts: float = 0.0
        self._live_interval_seconds: float = self._live_positions_interval()
        # بث حي للإشارات (كل الأزواج بما فيها WAIT)
        self._live_signals_msg_id: int | None = None
        self._live_signals_chat_id: str | None = None
        self._live_signals_enabled: bool = False
        self._live_signals_last_ts: float = 0.0
        self._live_signals_last_text: str = ""
        self._live_signals_interval_seconds: float = 15.0

    def update_market(
        self,
        entries: list[dict],
        prices: dict[str, float] | None = None,
        *,
        reasons: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        for entry in entries:
            self.market.entries[entry["symbol"]] = entry
        if prices:
            self.market.prices.update(prices)
        if reasons:
            self.market.reasons.update(reasons)

    def send_main_menu(self) -> int | None:
        view = self.render_main()
        return self.telegram.send_message(view.text, reply_markup=view.keyboard)

    def render_main(self) -> DashboardView:
        settings = get_settings()
        active_pairs = get_symbol_registry().active_pairs()
        state = self.risk.state
        balance = self.executor.get_account_balance()
        pnl = f"{state.daily_pnl_pct:+.2f}%" if state else "0.00%"
        kill = "مفعّل 🛑" if state and state.kill_switch_active else "طبيعي ✅"
        text = format_main_dashboard(
            env=settings.env,
            mode=settings.execution_mode,
            balance=balance,
            daily_pnl=pnl,
            open_count=self.executor.position_manager.count(),
            paused=self.runtime.paused,
            kill_switch=kill,
            pairs_count=len(active_pairs),
            manual_mode=self.runtime.manual_entry_required,
        )
        return DashboardView(text, main_menu_keyboard(paused=self.runtime.paused))

    def render_market(self) -> DashboardView:
        from operations.signal_filter import annotate_entry_actions

        active_pairs = get_symbol_registry().active_pairs()
        all_entries = [
            self.market.entries[s]
            for s in active_pairs
            if s in self.market.entries
        ]
        qualified = annotate_entry_actions(
            all_entries,
            open_positions=self.executor.position_manager.count(),
        )
        symbols = [e["symbol"] for e in qualified]
        return DashboardView(
            format_qualified_signals_digest(qualified),
            market_keyboard(symbols, entries=qualified)
            if symbols
            else {
                "inline_keyboard": [
                    [{"text": "🔄 تحديث", "callback_data": "view:market"}],
                    [{"text": "◀️ الرئيسية", "callback_data": "view:main"}],
                ]
            },
        )

    def render_watchlist_digest(self) -> DashboardView | None:
        active_pairs = get_symbol_registry().active_pairs()
        all_entries = [
            self.market.entries[s]
            for s in active_pairs
            if s in self.market.entries
        ]
        if not all_entries:
            return None
        return DashboardView(
            format_watchlist_digest(all_entries),
            market_keyboard([e["symbol"] for e in all_entries], entries=all_entries),
        )

    def render_positions(self, *, live: bool = True) -> DashboardView:
        positions = self.executor.position_manager.all()
        prices = dict(self.market.prices)
        symbols = [p.symbol for p in positions]
        if live and symbols:
            try:
                fresh = self._fetch_prices(symbols)
                prices.update(fresh)
                self.market.prices.update(fresh)
            except Exception as exc:  # noqa: BLE001
                logger.debug("live positions price fetch: %s", exc)
        for pos in positions:
            prices.setdefault(pos.symbol, pos.entry_price)

        interval = max(1, int(round(self._live_positions_interval())))
        header = (
            "🔴 <b>مراكزي — بث حي</b>\n"
            f"<i>يتحدّث السعر تلقائياً كل ~{interval} ثانية</i>\n\n"
        )
        body = format_positions_list(positions, prices)
        text = header + body if positions else body
        return DashboardView(
            text,
            positions_list_keyboard(positions, prices, live=True),
        )

    def _live_positions_interval(self) -> float:
        """فاصل تحديث بث المراكز الحي — افتراضي 1 ثانية."""
        import os

        raw = os.getenv("TELEGRAM_LIVE_POSITIONS_SECONDS", "1").strip()
        try:
            return max(1.0, float(raw or "1"))
        except (TypeError, ValueError):
            return 1.0

    def enable_live_positions(self, message_id: int, chat_id: str | None = None) -> None:
        self._live_positions_enabled = True
        self._live_positions_msg_id = message_id
        self._live_positions_chat_id = chat_id
        self._live_positions_last_ts = 0.0
        self._live_interval_seconds = self._live_positions_interval()

    def disable_live_positions(self) -> None:
        self._live_positions_enabled = False
        self._live_positions_msg_id = None
        self._live_positions_chat_id = None

    @property
    def live_positions_active(self) -> bool:
        return bool(
            self._live_positions_enabled and self._live_positions_msg_id is not None
        )

    def tick_live_positions(self) -> bool:
        """يحدّث رسالة المراكز الحية إن حان الوقت. يُستدعى من حلقة تيليجرام."""
        if not self.live_positions_active:
            return False
        now = time.monotonic()
        interval = self._live_positions_interval()
        self._live_interval_seconds = interval
        if now - self._live_positions_last_ts < interval:
            return False
        self._live_positions_last_ts = now
        try:
            view = self.render_positions(live=True)
            ok = self.telegram.edit_message_text(
                int(self._live_positions_msg_id),
                view.text,
                reply_markup=view.keyboard,
                chat_id=self._live_positions_chat_id,
            )
            return bool(ok)
        except Exception as exc:  # noqa: BLE001
            logger.debug("tick_live_positions: %s", exc)
            return False

    def _live_signals_wanted(self) -> bool:
        import os

        raw = os.getenv("TELEGRAM_LIVE_SIGNALS", "true").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _live_signals_interval(self) -> float:
        import os

        try:
            settings = get_settings()
            base = float(getattr(settings, "loop_interval_seconds", 15) or 15)
        except Exception:
            base = 15.0
        raw = os.getenv("TELEGRAM_LIVE_SIGNALS_SECONDS", "").strip()
        if raw:
            try:
                return max(5.0, float(raw))
            except ValueError:
                pass
        return max(5.0, base)

    def render_live_signals(self) -> DashboardView:
        from datetime import datetime, timezone

        active_pairs = get_symbol_registry().active_pairs()
        all_entries = [
            self.market.entries[s]
            for s in active_pairs
            if s in self.market.entries
        ]
        interval = int(self._live_signals_interval())
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        text = format_live_signals_board(
            all_entries,
            interval_seconds=interval,
            updated_at=stamp,
        )
        symbols = [e["symbol"] for e in all_entries]
        return DashboardView(
            text,
            market_keyboard(symbols, entries=all_entries)
            if symbols
            else {
                "inline_keyboard": [
                    [{"text": "🔄 تحديث", "callback_data": "view:market"}],
                    [{"text": "◀️ الرئيسية", "callback_data": "view:main"}],
                ]
            },
        )

    def ensure_live_signals(self) -> bool:
        """ينشئ رسالة بث حي للإشارات إن لم تكن موجودة."""
        if not self._live_signals_wanted():
            return False
        if self._live_signals_enabled and self._live_signals_msg_id is not None:
            return True
        try:
            view = self.render_live_signals()
            msg_id = self.telegram.send_message(view.text, reply_markup=view.keyboard)
            if msg_id is None:
                return False
            self._live_signals_enabled = True
            self._live_signals_msg_id = int(msg_id)
            self._live_signals_chat_id = None
            self._live_signals_last_ts = time.monotonic()
            self._live_signals_last_text = view.text
            self._live_signals_interval_seconds = self._live_signals_interval()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("ensure_live_signals: %s", exc)
            return False

    def publish_live_signals(self, *, force: bool = False) -> bool:
        """يحدّث لوحة الإشارات الحية بعد كل دورة تحليل."""
        if not self._live_signals_wanted():
            return False
        try:
            if not self.ensure_live_signals():
                return False
            now = time.monotonic()
            interval = self._live_signals_interval()
            self._live_signals_interval_seconds = interval
            if (
                not force
                and (now - self._live_signals_last_ts) < max(5.0, interval - 1.0)
            ):
                return False
            view = self.render_live_signals()
            if view.text == self._live_signals_last_text and not force:
                self._live_signals_last_ts = now
                return True
            self.telegram.edit_message_text(
                int(self._live_signals_msg_id),
                view.text,
                reply_markup=view.keyboard,
                chat_id=self._live_signals_chat_id,
            )
            # حتى لو «message is not modified» نعتبر التحديث ناجحاً
            self._live_signals_last_ts = now
            self._live_signals_last_text = view.text
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("publish_live_signals: %s", exc)
            return False

    def tick_live_signals(self) -> bool:
        """نبضة من خيط تيليجرام — يحافظ على التحديث كل ~15 ثانية."""
        if not self._live_signals_wanted():
            return False
        if not (self._live_signals_enabled and self._live_signals_msg_id is not None):
            return False
        return self.publish_live_signals(force=False)

    def render_report(self) -> DashboardView:
        text = format_daily_report_telegram(
            risk=self.risk,
            executor=self.executor,
            audit=self.audit,
        )
        return DashboardView(text, back_to_main_keyboard())

    def render_symbol(self, symbol: str) -> DashboardView:
        entry = self.market.entries.get(symbol)
        if entry is None:
            return DashboardView(
                format_action_result("الإشارات", f"لا بيانات حديثة لـ {symbol}"),
                back_to_main_keyboard(),
            )

        price = float(entry["price"])
        score = int(entry["score"])
        signal = str(entry["signal"])
        # عرض سريع: بدون Monte Carlo / evaluate_entry عند كل ضغطة
        balance = self.executor.get_account_balance()
        reasons = self.market.reasons.get(symbol, ())
        can_enter = (
            not self.runtime.paused
            and not self.executor.position_manager.has(symbol)
        )
        block_reason = ""
        if not can_enter:
            block_reason = format_entry_block_reason(
                signal=signal,
                score=score,
                premium=bool(entry.get("premium")),
                paused=self.runtime.paused,
                has_position=self.executor.position_manager.has(symbol),
                approval_approved=True,
                approval_reason="",
            )
        text = format_trade_setup_card(
            symbol=symbol,
            price=price,
            score=score,
            signal=signal,
            approval=None,
            reasons=reasons,
            can_enter=can_enter,
            entry_block_reason=block_reason,
            balance=balance,
        )
        return DashboardView(text, trade_entry_keyboard(symbol, can_enter=can_enter))

    def render_position(self, symbol: str) -> DashboardView:
        position = self.executor.position_manager.get(symbol)
        if position is None:
            return DashboardView(
                format_action_result("مراكزي", f"لا يوجد مركز مفتوح على {symbol}"),
                back_to_main_keyboard(),
            )
        # حدّث سعراً واحداً فقط عند فتح تفاصيل الصفقة
        live = self._fetch_prices([symbol])
        current = live.get(
            symbol,
            self.market.prices.get(symbol, position.entry_price),
        )
        if symbol in live:
            self.market.prices[symbol] = live[symbol]
        balance = self.executor.get_account_balance()
        return DashboardView(
            format_position_card(position, current_price=current, balance=balance),
            position_trade_keyboard(symbol),
        )

    def handle_callback(self, data: str) -> DashboardView:
        if data == "view:main":
            self.disable_live_positions()
            return self.render_main()
        if data == "view:market":
            self.disable_live_positions()
            return self.render_market()
        if data == "view:positions":
            try:
                from execution.binance_position_sync import sync_binance_spot_positions

                sync_binance_spot_positions(self.executor)
            except Exception as exc:  # noqa: BLE001
                logger.debug("positions sync on view: %s", exc)
            return self.render_positions(live=True)
        if data == "view:report":
            self.disable_live_positions()
            try:
                from execution.binance_position_sync import sync_binance_spot_positions

                sync_binance_spot_positions(self.executor)
            except Exception as exc:  # noqa: BLE001
                logger.debug("report sync: %s", exc)
            return self.render_report()
        if data == "act:pause":
            self.runtime.pause()
            return self.render_main()
        if data == "act:resume":
            if self.runtime.user_stopped:
                return DashboardView(
                    format_action_result("تشغيل", "البوت متوقف بقرارك — شغّل 00_START.bat"),
                    back_to_main_keyboard(),
                )
            self.runtime.resume()
            return self.render_main()
        if data == "act:close_all":
            symbols = list(self.executor.position_manager.open_symbols())
            if not symbols:
                return DashboardView(
                    format_action_result("إغلاق", "لا توجد مراكز مفتوحة."),
                    main_menu_keyboard(paused=self.runtime.paused),
                )
            # أسعار من الكاش أولاً لتسريع الاستجابة
            prices = dict(self.market.prices)
            missing = [s for s in symbols if s not in prices or prices.get(s, 0) <= 0]
            if missing:
                prices.update(self._fetch_prices(missing))
            closed: list[str] = []
            for symbol in symbols:
                position = self.executor.position_manager.get(symbol)
                if position is None:
                    continue
                price = prices.get(symbol) or position.entry_price
                if self.executor.close_position(
                    symbol, float(price), reason="إغلاق الكل — لوحة التحكم"
                ):
                    closed.append(symbol)
            return DashboardView(
                format_action_result(
                    "إغلاق الكل ✅",
                    f"أُغلق {len(closed)} مركز: {', '.join(closed) if closed else '—'}",
                ),
                main_menu_keyboard(paused=self.runtime.paused),
            )
        if data == "act:panic":
            # أغلق أولاً وحدّث الواجهة؛ الإيقاف الدائم بعد إرجاع الرسالة
            symbols = list(self.executor.position_manager.open_symbols())
            prices = dict(self.market.prices)
            missing = [s for s in symbols if s not in prices or prices.get(s, 0) <= 0]
            if missing:
                try:
                    prices.update(self._fetch_prices(missing))
                except Exception:
                    pass
            try:
                self.panic.trigger(prices, reason="لوحة التحكم — طوارئ")
            except Exception as exc:
                logger.warning("panic.trigger فشل: %s", exc)
            view = DashboardView(
                format_action_result(
                    "طوارئ",
                    "تم إغلاق المراكز المتاحة. إيقاف كامل — شغّل 00_START.bat للعودة.",
                ),
                main_menu_keyboard(paused=True),
            )
            # أوقف بعد تجهيز الرسالة حتى يصل الرد للمستخدم
            try:
                self.runtime.stop_permanently(reason="dashboard_panic")
            except Exception as exc:
                logger.warning("stop_permanently فشل: %s", exc)
            return view
        if data.startswith("sym:"):
            return self.render_symbol(decode_symbol(data.split(":", 1)[1]))
        if data.startswith("pos:"):
            return self.render_position(decode_symbol(data.split(":", 1)[1]))
        if data.startswith("close:"):
            return self._close_position(decode_symbol(data.split(":", 1)[1]))
        if data.startswith("enter:"):
            return self._manual_enter(decode_symbol(data.split(":", 1)[1]))
        return self.render_main()

    def _close_position(self, symbol: str) -> DashboardView:
        position = self.executor.position_manager.get(symbol)
        if position is None:
            return DashboardView(
                format_action_result("إغلاق", f"لا مركز على {symbol}"),
                back_to_main_keyboard(),
            )
        prices = self._fetch_prices([symbol])
        price = prices.get(symbol, self.market.prices.get(symbol, position.entry_price))
        closed = self.executor.close_position(symbol, price, reason="إغلاق يدوي — لوحة التحكم")
        if closed:
            return DashboardView(
                format_action_result("إغلاق ناجح ✅", f"تم إغلاق {symbol} @ {price:,.2f}"),
                back_to_main_keyboard(),
            )
        return DashboardView(
            format_action_result("إغلاق", f"تعذر إغلاق {symbol}"),
            back_to_main_keyboard(),
        )

    def _manual_enter(self, symbol: str) -> DashboardView:
        """دخول إجباري — يفتح الصفقة حتى لو الدرجة ضعيفة (Binance Demo)."""
        from core.analyzer import AnalysisResult

        if self.runtime.paused:
            return DashboardView(
                format_action_result("دخول", "التداول موقوف — اضغط ▶️ تشغيل أولاً."),
                back_to_main_keyboard(),
            )
        if self.executor.position_manager.has(symbol):
            return DashboardView(
                format_action_result("دخول", f"يوجد مركز مفتوح على {symbol}"),
                back_to_main_keyboard(),
            )

        cached = self.market.entries.get(symbol) or {}
        price = float(cached.get("price") or self.market.prices.get(symbol) or 0.0)
        score = int(cached.get("score") or 0)
        signal = str(cached.get("signal") or "WAIT")
        live = None

        try:
            live = MarketAnalyzer(symbol=symbol).analyze()
            if live.price > 0:
                price = live.price
            score = max(score, int(live.score or 0))
            if live.signal in {"BUY SIGNAL", "SELL SIGNAL"}:
                signal = live.signal
        except Exception:
            logger.exception("تحليل الدخول الإجباري لـ %s — نكمل باللقطة", symbol)

        if signal not in {"BUY SIGNAL", "SELL SIGNAL"}:
            if cached.get("signal") in {"BUY SIGNAL", "SELL SIGNAL"}:
                signal = str(cached["signal"])
            else:
                signal = "BUY SIGNAL"

        if price <= 0:
            return DashboardView(
                format_action_result("دخول", "لا يوجد سعر صالح لهذا الزوج الآن."),
                trade_entry_keyboard(symbol, can_enter=True),
            )

        result = AnalysisResult(
            symbol=symbol,
            signal=signal,
            price=price,
            sma=getattr(live, "sma", 0.0) or 0.0,
            score=score,
            passed=True,
            reasons=("دخول إجباري من لوحة تيليجرام",),
            alignment=getattr(live, "alignment", None),
            score_breakdown=getattr(live, "score_breakdown", None),
        )

        snapshot = None
        consensus = None
        if self.audit is not None:
            try:
                snapshot, consensus = self.audit.record_market_check(result)
            except Exception:
                logger.exception("تدقيق الدخول الإجباري — نكمل التنفيذ")

        exec_result = self.executor.try_open(
            result,
            snapshot=snapshot,
            consensus=consensus,
            manual_force=True,
        )
        if exec_result.executed:
            if self.executor.alerts is not None:
                self.executor.alerts.trade_opened(symbol, exec_result.message)
            view = self.render_position(symbol)
            text = (
                f"✅ <b>تم فتح الصفقة إجبارياً</b>\n"
                f"<i>{escape(exec_result.message)}</i>\n"
                f"{DIVIDER}\n"
                f"{view.text}"
            )
            return DashboardView(text, view.keyboard)

        reason = exec_result.reason or exec_result.message or "سبب غير معروف"
        detail = (
            f"الزوج: {symbol}\n"
            f"السبب: {reason}\n"
            f"السعر: {price:.6f} · الدرجة: {score}/10 · الإشارة: {signal}\n"
            "لم تُفتح الصفقة. يمكنك المحاولة لاحقاً أو اختيار زوج آخر."
        )
        return DashboardView(
            format_action_result("رفض الدخول الإجباري", detail),
            trade_entry_keyboard(symbol, can_enter=True),
        )

    def build_trade_alert(self, symbol: str, entry: dict, reasons: tuple[str, ...] = ()) -> DashboardView:
        price = float(entry["price"])
        score = int(entry["score"])
        signal = str(entry["signal"])
        balance = self.executor.get_account_balance()
        side = "sell" if signal == "SELL SIGNAL" else "buy"
        approval = self.risk.evaluate_entry(
            symbol, price, balance, signal_score=score, side=side
        )
        # يدوي: متاح لأي درجة ما دام ما فيه مركز ولا إيقاف
        can_enter = (
            not self.runtime.paused
            and not self.executor.position_manager.has(symbol)
        )
        block_reason = ""
        if not can_enter:
            block_reason = format_entry_block_reason(
                signal=signal,
                score=score,
                premium=bool(entry.get("premium")),
                paused=self.runtime.paused,
                has_position=self.executor.position_manager.has(symbol),
                approval_approved=True,
                approval_reason="",
            )
        text = format_trade_setup_card(
            symbol=symbol,
            price=price,
            score=score,
            signal=signal,
            approval=approval,
            reasons=reasons,
            can_enter=can_enter,
            entry_block_reason=block_reason,
            balance=balance,
        )
        return DashboardView(text, trade_entry_keyboard(symbol, can_enter=can_enter))

    def _fetch_prices(self, symbols: list[str]) -> dict[str, float]:
        if self._price_fetcher is None:
            return {}
        return self._price_fetcher(symbols)
