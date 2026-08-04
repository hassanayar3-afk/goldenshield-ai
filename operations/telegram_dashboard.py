"""لوحة تحكم Telegram — حسب دستور GoldenShield.

قواعد المشروع الثابتة (لا تُعدَّل من اللوحة):
- مخاطرة 1% لكل صفقة (المرحلة 6)
- SL 3% / R:R 1:2 (المرحلة 5)
- Breakeven تلقائي عند 1:1 + خروج جزئي (المرحلة 5)
- دخول فقط بدرجة ≥75%
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from config.settings import get_settings
from core.analyzer import MarketAnalyzer
from operations.dashboard_templates import (
    compute_open_floating_pnl,
    format_action_result,
    format_closed_trades_history,
    format_entry_block_reason,
    format_live_signals_board,
    format_main_dashboard,
    format_position_card,
    format_positions_list,
    format_qualified_signals_digest,
    format_trade_setup_card,
    format_watchlist_digest,
    write_console_signals_board_file,
)
from operations.daily_report import format_daily_report_telegram
from operations.message_templates import DIVIDER, escape
from operations.symbol_registry import get_symbol_registry
from operations.telegram_keyboards import (
    back_to_main_keyboard,
    close_menu_keyboard,
    decode_symbol,
    encode_symbol,
    history_keyboard,
    main_menu_keyboard,
    market_keyboard,
    position_trade_keyboard,
    positions_list_keyboard,
    report_period_keyboard,
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
        self._live_signals_last_body: str = ""
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

    def _live_open_ssot(self, *, reason: str = "dashboard") -> tuple[list, int]:
        """مصدر الحقيقة الوحيد للوحة: نفس القائمة ونفس العدد من Binance."""
        try:
            from execution.binance_position_sync import get_live_open_positions_ssot

            positions, count = get_live_open_positions_ssot(self.executor)
            self._last_spot_sync_ts = time.monotonic()
            return list(positions or []), int(count or 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("live open ssot (%s): %s", reason, exc)
            return [], 0

    def _mirror_live_spot_state(self, *, reason: str = "dashboard") -> int:
        """مرآة حية عبر SSoT — العدد من المنصة فقط."""
        _, count = self._live_open_ssot(reason=reason)
        return int(count)

    def _maybe_sync_spot_holdings(self, *, force: bool = False) -> None:
        """توافق خلفي — لوحة التحكم تستخدم المرآة الحية دائماً."""
        try:
            if force:
                self._live_open_ssot(reason="force_sync")
                return
            now = time.monotonic()
            last = float(getattr(self, "_last_spot_sync_ts", 0.0) or 0.0)
            if (now - last) < 0.8:
                return
            self._live_open_ssot(reason="dashboard_sync")
        except Exception as exc:  # noqa: BLE001
            logger.debug("spot holdings sync: %s", exc)

    def render_main(self) -> DashboardView:
        """لوحة رئيسية — المفتوحة من نفس SSoT المستخدم في مراكزي."""
        positions, open_count = self._live_open_ssot(reason="render_main")

        settings = get_settings()
        active_pairs = get_symbol_registry().active_pairs()
        state = self.risk.state
        balance = self.executor.get_account_balance()
        pnl = f"{state.daily_pnl_pct:+.2f}%" if state else "0.00%"
        kill = "مفعّل 🛑" if state and state.kill_switch_active else "طبيعي ✅"
        prices = dict(self.market.prices)
        for pos in positions:
            prices.setdefault(pos.symbol, pos.entry_price)
        floating = None
        try:
            if open_count > 0 and positions:
                floating, _ = compute_open_floating_pnl(positions, prices)
        except Exception:
            floating = None
        text = format_main_dashboard(
            env=settings.env,
            mode=settings.execution_mode,
            balance=balance,
            daily_pnl=pnl,
            open_count=open_count,
            paused=self.runtime.paused,
            kill_switch=kill,
            pairs_count=len(active_pairs),
            manual_mode=self.runtime.manual_entry_required,
            floating_pnl=floating,
        )
        return DashboardView(text, main_menu_keyboard(paused=self.runtime.paused))

    def render_market(self) -> DashboardView:
        from operations.signal_filter import annotate_entry_actions

        _, open_count = self._live_open_ssot(reason="render_market")
        active_pairs = get_symbol_registry().active_pairs()
        all_entries = [
            self.market.entries[s]
            for s in active_pairs
            if s in self.market.entries
        ]
        qualified = annotate_entry_actions(
            all_entries,
            open_positions=open_count,
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
        # نفس مصدر الحقيقة الوحيد المستخدم في اللوحة الرئيسية
        positions, open_count = self._live_open_ssot(reason="render_positions")

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
            "📂 <b>مراكزي</b> — بث حي\n"
            f"<i>تحديث السعر كل ~{interval} ثانية · المفتوحة: {open_count}</i>\n\n"
        )
        live_scores = {
            sym: int(e.get("score", 0) or 0)
            for sym, e in self.market.entries.items()
        }
        for pos in positions:
            if int(getattr(pos, "signal_score", 0) or 0) <= 0:
                sc = int(live_scores.get(pos.symbol, 0) or 0)
                if sc > 0:
                    pos.signal_score = sc
                    try:
                        self.executor._persist_open_trade(pos)  # noqa: SLF001
                    except Exception:
                        pass
        body = format_positions_list(positions, prices, live_scores=live_scores)
        if open_count <= 0 or not positions:
            body = (
                "لا توجد مراكز مفتوحة على المنصة حالياً.\n"
                "العداد هنا مطابق للوحة الرئيسية ومصدره Binance مباشرة."
            )
        text = header + body
        return DashboardView(
            text,
            positions_list_keyboard(
                positions, prices, live=True, live_scores=live_scores
            ),
        )

    def _live_positions_interval(self) -> float:
        """فاصل تحديث بث المراكز على تيليجرام — هدف ~1ث مع سقف ضد 429."""
        raw = os.getenv("TELEGRAM_LIVE_POSITIONS_SECONDS", "1").strip()
        try:
            return max(1.0, min(float(raw or "1"), 60.0))
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
        raw = os.getenv("TELEGRAM_LIVE_SIGNALS", "true").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _live_signals_interval(self) -> float:
        """فاصل تحديث رسالة تيليجرام للإشارات — آمن ضد 429 (افتراضي 15ث).

        سرعة CMD منفصلة عبر signals_board.txt ولا تعتمد على هذا الفاصل العدواني.
        """
        raw = os.getenv("TELEGRAM_LIVE_SIGNALS_SECONDS", "15").strip()
        try:
            return max(5.0, min(float(raw or "15"), 60.0))
        except (TypeError, ValueError):
            return 15.0

    def render_live_signals(self, *, refresh_prices: bool = False) -> DashboardView:
        from datetime import datetime, timezone

        active_pairs = get_symbol_registry().active_pairs()
        if refresh_prices:
            try:
                prices = self._fetch_prices(list(active_pairs))
                if prices:
                    self.market.prices.update(prices)
                    for sym, px in prices.items():
                        if sym in self.market.entries:
                            self.market.entries[sym]["price"] = float(px)
            except Exception as exc:  # noqa: BLE001
                logger.debug("live signals price refresh: %s", exc)

        all_entries = [
            self.market.entries[s]
            for s in active_pairs
            if s in self.market.entries
        ]
        interval = self._live_signals_interval()
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S") + " UTC"
        text = format_live_signals_board(
            all_entries,
            interval_seconds=interval,
            updated_at=stamp,
        )
        try:
            write_console_signals_board_file(
                all_entries,
                interval_seconds=interval,
                updated_at=stamp,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("write_console_signals_board_file: %s", exc)
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

    @staticmethod
    def _board_body_key(text: str) -> str:
        """مقارنة محتوى اللوحة بدون ختم الوقت — يمنع تعديل تيليجرام كل نبضة."""
        lines = []
        for line in str(text or "").splitlines():
            if (
                "آخر تحديث" in line
                or "Updated" in line
                or ("UTC" in line and ":" in line)
            ):
                continue
            lines.append(line)
        return "\n".join(lines)

    def ensure_live_signals(self) -> bool:
        """ينشئ رسالة بث حي للإشارات إن لم تكن موجودة."""
        if not self._live_signals_wanted():
            return False
        if self._live_signals_enabled and self._live_signals_msg_id is not None:
            return True
        try:
            if getattr(self.telegram, "flood_active", lambda: False)():
                return False
            view = self.render_live_signals(refresh_prices=False)
            msg_id = self.telegram.send_message(view.text, reply_markup=view.keyboard)
            if msg_id is None:
                return False
            self._live_signals_enabled = True
            self._live_signals_msg_id = int(msg_id)
            self._live_signals_chat_id = None
            self._live_signals_last_ts = time.monotonic()
            self._live_signals_last_text = view.text
            self._live_signals_last_body = self._board_body_key(view.text)
            self._live_signals_interval_seconds = self._live_signals_interval()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("ensure_live_signals: %s", exc)
            return False

    def publish_live_signals(self, *, force: bool = False) -> bool:
        """يحدّث لوحة إشارات تيليجرام بفاصل آمن — الأزرار لها الأولوية."""
        if not self._live_signals_wanted():
            return False
        try:
            if getattr(self.telegram, "flood_active", lambda: False)():
                # أثناء 429: حدّث ملف CMD فقط بدون editMessageText
                try:
                    self.render_live_signals(refresh_prices=False)
                except Exception:
                    pass
                return False
            if not self.ensure_live_signals():
                return False
            now = time.monotonic()
            interval = self._live_signals_interval()
            self._live_signals_interval_seconds = interval
            if not force and (now - self._live_signals_last_ts) < interval:
                return False
            view = self.render_live_signals(refresh_prices=False)
            body_key = self._board_body_key(view.text)
            last_body = getattr(self, "_live_signals_last_body", "")
            if body_key == last_body and not force:
                self._live_signals_last_ts = now
                return True
            ok = self.telegram.edit_message_text(
                int(self._live_signals_msg_id),
                view.text,
                reply_markup=view.keyboard,
                chat_id=self._live_signals_chat_id,
            )
            self._live_signals_last_ts = now
            if ok:
                self._live_signals_last_text = view.text
                self._live_signals_last_body = body_key
            return bool(ok)
        except Exception as exc:  # noqa: BLE001
            logger.debug("publish_live_signals: %s", exc)
            return False

    def tick_live_signals(self) -> bool:
        """نبضة من خيط تيليجرام — تحديث آمن لا يخنق الأزرار."""
        if not self._live_signals_wanted():
            return False
        if getattr(self.telegram, "flood_active", lambda: False)():
            try:
                self.render_live_signals(refresh_prices=False)
            except Exception:
                pass
            return False
        if not (self._live_signals_enabled and self._live_signals_msg_id is not None):
            return self.ensure_live_signals()
        return self.publish_live_signals(force=False)

    def render_report(self) -> DashboardView:
        text = format_daily_report_telegram(
            risk=self.risk,
            executor=self.executor,
            audit=self.audit,
        )
        try:
            repo = getattr(self.executor, "trade_repo", None)
            if repo is not None:
                summary = repo.trade_history_summary()
                closed = repo.list_closed_trades(limit=15)
                hist = format_closed_trades_history(
                    closed, summary=summary, limit_shown=15
                )
                text = f"{text}\n\n{DIVIDER}\n{hist}"
        except Exception as exc:  # noqa: BLE001
            logger.debug("history in report: %s", exc)
        return DashboardView(text, report_period_keyboard())

    def render_period_report(self, kind: str) -> DashboardView:
        """تقرير أسبوع/شهر من سجل DB الدائم."""
        try:
            from operations.period_report import analyze_period_trades, period_bounds

            label, from_iso, to_iso = period_bounds(kind)
            repo = getattr(self.executor, "trade_repo", None)
            trades = []
            if repo is not None and hasattr(repo, "list_closed_trades_between"):
                trades = repo.list_closed_trades_between(from_iso, to_iso, limit=300)
            elif repo is not None:
                # توافق خلفي: صفّ من آخر المغلقات
                trades = [
                    t
                    for t in repo.list_closed_trades(limit=300)
                    if (getattr(t, "closed_at", None) or getattr(t, "opened_at", "") or "")
                    >= from_iso
                ]
            text = analyze_period_trades(trades, label=label)
        except Exception as exc:  # noqa: BLE001
            logger.exception("render_period_report: %s", exc)
            text = format_action_result("تقرير الفترة", f"تعذّر البناء: {exc}")
        return DashboardView(text, report_period_keyboard())

    def render_trade_history(self) -> DashboardView:
        """عرض الصفقات المغلقة دائماً — لا تختفي بعد الإغلاق."""
        self.disable_live_positions()
        repo = getattr(self.executor, "trade_repo", None)
        if repo is None:
            return DashboardView(
                format_action_result(
                    "سجل الصفقات",
                    "قاعدة البيانات غير متصلة — لا يمكن عرض السجل الآن.",
                ),
                back_to_main_keyboard(),
            )
        try:
            summary = repo.trade_history_summary()
            closed = repo.list_closed_trades(limit=80)
            text = format_closed_trades_history(
                closed, summary=summary, limit_shown=40
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("render_trade_history: %s", exc)
            text = format_action_result("سجل الصفقات", f"تعذّر القراءة: {exc}")
        return DashboardView(text, history_keyboard())

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
        has_pos = self.executor.position_manager.has(symbol)
        # Spot: إشارة بيع مع مركز طويل = خروج مسموح (وليس فتح شورت)
        sell_exit = signal == "SELL SIGNAL" and has_pos
        can_enter = (not self.runtime.paused) and ((not has_pos) or sell_exit)
        block_reason = ""
        if not can_enter:
            block_reason = format_entry_block_reason(
                signal=signal,
                score=score,
                premium=bool(entry.get("premium")),
                paused=self.runtime.paused,
                has_position=has_pos,
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
        live_score = 0
        entry = self.market.entries.get(symbol) or {}
        try:
            live_score = int(entry.get("score", 0) or 0)
        except (TypeError, ValueError):
            live_score = 0
        if int(getattr(position, "signal_score", 0) or 0) <= 0 and live_score > 0:
            position.signal_score = live_score
            try:
                self.executor._persist_open_trade(position)  # noqa: SLF001
            except Exception:
                pass
        return DashboardView(
            format_position_card(
                position,
                current_price=current,
                balance=balance,
                live_score=live_score,
            ),
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
            return self.render_positions(live=True)
        if data == "view:history":
            return self.render_trade_history()
        if data == "view:report":
            self.disable_live_positions()
            return self.render_report()
        if data in {"view:report_week", "view:report_month"}:
            self.disable_live_positions()
            kind = "week" if data.endswith("week") else "month"
            return self.render_period_report(kind)
        if data == "view:close_menu":
            self.disable_live_positions()
            return DashboardView(
                format_action_result(
                    "إغلاق الصفقات",
                    "اختر نوع الإغلاق:\n"
                    "🟢 الرابحة فقط · 🔴 الخاسرة فقط · ❌ الجميع",
                ),
                close_menu_keyboard(),
            )
        if data == "act:pause":
            # مع BOT_FORCE_ACTIVE=true لا يُسمح بالسكون — الإشارات يجب أن تستمر
            if (os.getenv("BOT_FORCE_ACTIVE", "true") or "true").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }:
                self.runtime.resume()
                return DashboardView(
                    format_action_result(
                        "تشغيل دائم",
                        "وضع السكون معطّل — البوت يبقى نشطاً والإشارات مستمرة.\n"
                        "لإيقاف الدخول فقط استخدم طوارئ إن لزم، أو عطّل BOT_FORCE_ACTIVE.",
                    ),
                    main_menu_keyboard(paused=False),
                )
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
        if data in {"act:close_all", "act:close_winners", "act:close_losers"}:
            mode = (
                "all"
                if data == "act:close_all"
                else ("winners" if data == "act:close_winners" else "losers")
            )
            return self._close_filtered(mode)
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

    def _close_filtered(self, mode: str) -> DashboardView:
        """إغلاق حسب الفلتر: all | winners | losers."""
        positions, open_before = self._live_open_ssot(reason="close_filtered_before")
        if not positions:
            return DashboardView(
                format_action_result(
                    "إغلاق",
                    f"لا توجد مراكز مفتوحة على المنصة (المفتوحة الآن: {open_before}).",
                ),
                main_menu_keyboard(paused=self.runtime.paused),
            )
        symbols = [p.symbol for p in positions]
        prices = dict(self.market.prices)
        missing = [s for s in symbols if s not in prices or float(prices.get(s) or 0) <= 0]
        if missing:
            try:
                prices.update(self._fetch_prices(missing))
            except Exception:
                pass

        def _pnl(pos) -> float:
            px = float(prices.get(pos.symbol) or pos.entry_price or 0)
            if str(getattr(pos.side, "value", pos.side)).lower() == "buy":
                return (px - float(pos.entry_price)) * float(pos.amount)
            return (float(pos.entry_price) - px) * float(pos.amount)

        selected = []
        for pos in positions:
            pnl = _pnl(pos)
            if mode == "winners" and pnl <= 0:
                continue
            if mode == "losers" and pnl >= 0:
                continue
            selected.append(pos)

        if not selected:
            label = {
                "winners": "لا توجد صفقات رابحة الآن.",
                "losers": "لا توجد صفقات خاسرة الآن.",
            }.get(mode, "لا مراكز مطابقة.")
            return DashboardView(
                format_action_result("إغلاق", label),
                close_menu_keyboard(),
            )

        closed: list[str] = []
        failed: list[str] = []
        reason = {
            "all": "إغلاق الكل — لوحة التحكم",
            "winners": "إغلاق الرابحة — لوحة التحكم",
            "losers": "إغلاق الخاسرة — لوحة التحكم",
        }.get(mode, "إغلاق — لوحة التحكم")
        for pos in selected:
            price = float(prices.get(pos.symbol) or pos.entry_price or 0)
            try:
                if self.executor.close_position(pos.symbol, price, reason=reason):
                    closed.append(pos.symbol)
                else:
                    failed.append(pos.symbol)
            except Exception as close_exc:  # noqa: BLE001
                logger.warning("close_filtered %s %s: %s", mode, pos.symbol, close_exc)
                failed.append(pos.symbol)

        # مرآة فورية بعد الإغلاق — العداد من المنصة لا من الذاكرة القديمة
        open_after = self._mirror_live_spot_state(reason="close_filtered_after")
        title = {
            "all": "إغلاق الكل",
            "winners": "إغلاق الرابحة",
            "losers": "إغلاق الخاسرة",
        }.get(mode, "إغلاق")
        detail = f"أُغلق {len(closed)} مركز"
        if closed:
            detail += f": {', '.join(closed)}"
        if failed:
            detail += f"\nتعذّر: {', '.join(failed)}"
        detail += f"\n📂 المفتوحة الآن على المنصة: <b>{open_after}</b>"
        return DashboardView(
            format_action_result(title, detail),
            main_menu_keyboard(paused=self.runtime.paused),
        )

    def _close_position(self, symbol: str) -> DashboardView:
        positions, _ = self._live_open_ssot(reason="close_one_before")
        position = next((p for p in positions if p.symbol == symbol), None)
        if position is None:
            position = self.executor.position_manager.get(symbol)
        if position is None:
            _, open_now = self._live_open_ssot(reason="close_one_missing")
            return DashboardView(
                format_action_result(
                    "إغلاق",
                    f"لا مركز على {symbol} في المنصة.\n"
                    f"📂 المفتوحة الآن: <b>{open_now}</b>",
                ),
                back_to_main_keyboard(),
            )
        prices = self._fetch_prices([symbol])
        price = prices.get(symbol, self.market.prices.get(symbol, position.entry_price))
        try:
            closed = self.executor.close_position(
                symbol, price, reason="إغلاق يدوي — لوحة التحكم"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("إغلاق يدوي فشل %s: %s", symbol, exc)
            open_now = self._mirror_live_spot_state(reason="close_one_fail")
            return DashboardView(
                format_action_result(
                    "إغلاق فشل",
                    f"{symbol}\n{exc}\n📂 المفتوحة الآن: <b>{open_now}</b>",
                ),
                back_to_main_keyboard(),
            )
        open_after = self._mirror_live_spot_state(reason="close_one_after")
        if closed:
            return DashboardView(
                format_action_result(
                    "إغلاق ناجح ✅",
                    f"تم إغلاق {symbol} @ {price:,.2f}\n"
                    f"📂 المفتوحة الآن على المنصة: <b>{open_after}</b>",
                ),
                back_to_main_keyboard(),
            )
        return DashboardView(
            format_action_result(
                "إغلاق",
                f"تعذر إغلاق {symbol}\n📂 المفتوحة الآن: <b>{open_after}</b>",
            ),
            back_to_main_keyboard(),
        )

    def _manual_enter(self, symbol: str) -> DashboardView:
        """دخول إجباري — يفتح الصفقة حتى لو الدرجة ضعيفة (Binance Demo)."""
        from core.analyzer import AnalysisResult
        from execution.models.order import OrderSide

        if self.runtime.paused:
            return DashboardView(
                format_action_result("دخول", "التداول موقوف — اضغط ▶️ تشغيل أولاً."),
                back_to_main_keyboard(),
            )

        self._mirror_live_spot_state(reason="manual_enter")

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

        # Spot: بيع على مركز طويل موجود = إغلاق وليس رفض
        existing = self.executor.position_manager.get(symbol)
        if existing is not None:
            if signal == "SELL SIGNAL" and existing.side == OrderSide.BUY:
                return self._close_position(symbol)
            return DashboardView(
                format_action_result(
                    "دخول",
                    f"يوجد مركز مفتوح على {symbol}. للإغلاق استخدم مراكزي ← إغلاق.",
                ),
                position_trade_keyboard(symbol),
            )

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
