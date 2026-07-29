"""منسق المخاطر — بوابة إلزامية قبل كل صفقة."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from config.settings import get_settings
from core.constants import SIGNAL_MIN_PERCENT, meets_signal_minimum
from data.connection_monitor import ConnectionMonitor
from risk.compound_growth import effective_risk_pct
from risk.daily_limits import check_daily_limits
from risk.gradual_scaling import scaling_multiplier
from risk.heartbeat_guard import check_heartbeat_guard
from risk.inspection_mode import check_inspection_mode
from risk.kill_switch import check_kill_switch
from risk.loss_streak_guard import check_loss_streak
from risk.lot_calculator import LotCalculator
from risk.monte_carlo import run_monte_carlo
from risk.protocol_models import RISK_MODE_HIGH_CONVICTION, ProtocolApproval
from risk.rate_limiter import check_rate_limit, prune_open_timestamps
from risk.state import RiskState
from risk.trade_cooldown import (
    check_post_trade_cooldown,
    compute_post_trade_cooldown_until,
)
from core.fundamental.news_filter import check_news_filter
from core.technical.session_filter import check_kill_zones



@dataclass(frozen=True)
class RiskApproval:
    approved: bool
    reason: str
    amount: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


class RiskOrchestrator:
    def __init__(
        self,
        *,
        state: RiskState | None = None,
        connection_monitor: ConnectionMonitor | None = None,
        persist_callback=None,
    ) -> None:
        self.connection_monitor = connection_monitor
        self._state = state
        self._session_day = date.today() if state is not None else None
        self._persist_callback = persist_callback

    @property
    def state(self) -> RiskState | None:
        return self._state

    @property
    def session_day(self) -> date | None:
        return self._session_day

    def set_persist_callback(self, callback) -> None:
        self._persist_callback = callback

    def restore_state(self, state: RiskState, session_day: date | None = None) -> None:
        self._state = state
        self._session_day = session_day or date.today()

    def _persist(self) -> None:
        if self._persist_callback is not None and self._state is not None:
            self._persist_callback(self._state, self._session_day)

    def initialize(self, balance: float) -> None:
        self._state = RiskState(
            session_start_balance=balance,
            current_balance=balance,
        )
        self._session_day = date.today()
        self._persist()

    def ensure_state(self, balance: float) -> RiskState:
        today = date.today()
        if self._state is None:
            self.initialize(balance)
        elif self._session_day != today:
            self._state.reset_daily(self._state.current_balance)
            self._session_day = today
            self._persist()

        assert self._state is not None
        return self._state

    def evaluate_entry(
        self,
        symbol: str,
        entry_price: float,
        balance: float,
        *,
        signal_score: int,
        side: str = "buy",
        prefs=None,
        protocol: ProtocolApproval | None = None,
    ) -> RiskApproval:
        state = self.ensure_state(balance)
        settings = get_settings()

        if balance < settings.min_account_balance:
            return RiskApproval(
                False,
                f"الرصيد {balance:.2f} أقل من الحد الأدنى {settings.min_account_balance}",
            )

        if self.connection_monitor is not None:
            heartbeat = check_heartbeat_guard(self.connection_monitor)
            if not heartbeat.safe:
                # الدورة الطويلة قد تتجاوز timeout — جرّب نبضة حية قبل الرفض
                self.connection_monitor.heartbeat()
                heartbeat = check_heartbeat_guard(self.connection_monitor)
            if not heartbeat.safe:
                return RiskApproval(False, heartbeat.reason)

        if state.kill_switch_active:
            return RiskApproval(False, "Kill Switch مفعّل — تداول موقوف")

        kill = check_kill_switch(state.daily_pnl_pct)
        if kill.triggered:
            state.kill_switch_active = True
            self._persist()
            return RiskApproval(False, kill.reason)

        streak = check_loss_streak(state.consecutive_losses, state.cooldown_until)
        if streak.in_cooldown:
            if streak.cooldown_until and state.cooldown_until is None:
                state.cooldown_until = streak.cooldown_until
                self._persist()
            return RiskApproval(False, streak.reason)

        limits = check_daily_limits(state.daily_trades)
        if not limits.allowed:
            return RiskApproval(False, limits.reason)

        # تهدئة عامة بعد أي صفقة مغلقة
        post_cd = check_post_trade_cooldown(state.post_trade_cooldown_until)
        if post_cd.in_cooldown:
            return RiskApproval(False, post_cd.reason)

        # سقف العمليات: حد أقصى للصفقات في الساعة
        state.trade_open_timestamps = prune_open_timestamps(state.trade_open_timestamps)
        rate = check_rate_limit(
            state.trade_open_timestamps,
            max_per_hour=settings.max_trades_per_hour,
        )
        if not rate.allowed:
            return RiskApproval(False, rate.reason)

        # أمان: Kill Zones + فلتر الأخبار (15 دقيقة افتراضياً)
        safety = self.check_safety_gates()
        if not safety.approved:
            return RiskApproval(False, safety.reason)

        inspection = check_inspection_mode()
        if inspection.active and not meets_signal_minimum(signal_score):
            return RiskApproval(
                False,
                f"تفتيش: الدرجة أقل من {SIGNAL_MIN_PERCENT}/100",
            )

        mc_seed = hash(f"{symbol}:{date.today().isoformat()}") % 10000
        mc = run_monte_carlo(
            win_probability=min(0.55, 0.38 + signal_score * 0.01),
            seed=mc_seed,
        )
        # مرحلة التجربة: لا ترفض الصفقة بسبب محاكاة عشوائية
        if not mc.passed and not settings.trial_mode:
            return RiskApproval(False, mc.reason)

        hc_mode = protocol is not None and protocol.approved and protocol.risk_mode == RISK_MODE_HIGH_CONVICTION
        scale = 1.0 if hc_mode else scaling_multiplier(
            state.session_start_balance, state.current_balance
        )
        lot_calc = LotCalculator(state.current_balance)
        sl_pct = prefs.sl_pct if prefs is not None else None
        rr_ratio = prefs.rr_ratio if prefs is not None else None
        risk_pct = prefs.risk_pct if prefs is not None else None
        if risk_pct is None and not hc_mode:
            risk_pct = effective_risk_pct(
                None,
                consecutive_wins=int(getattr(state, "consecutive_wins", 0) or 0),
                consecutive_losses=int(state.consecutive_losses or 0),
            )
            try:
                from risk.advanced_shields import vol_adjusted_risk_pct
                from risk.emergency_protocols import fetch_live_atr

                atr_val = fetch_live_atr(symbol)
                risk_pct = vol_adjusted_risk_pct(
                    float(risk_pct),
                    atr=atr_val,
                    price=entry_price,
                ).risk_pct
            except Exception:
                pass
        amount, stop_loss, take_profit = lot_calc.calculate(
            entry_price,
            sl_pct=sl_pct,
            rr_ratio=rr_ratio,
            risk_pct=risk_pct,
            side=side,
        )
        amount = round(amount * scale, 8)

        if amount <= 0:
            return RiskApproval(False, "حجم العقد صفر بعد حساب المخاطر")

        if not lot_calc.is_rr_acceptable(entry_price, stop_loss, take_profit):
            return RiskApproval(False, "نسبة المخاطرة/العائد غير مقبولة")

        # —— طبقات مؤسسية مضافة (افتراضي: معطّلة) ——
        try:
            from risk.adx_filter import check_adx_filter
            from risk.micro_simulation import run_micro_simulation
            from risk.panic_mode import check_panic_mode
            from risk.profit_cap import check_profit_cap

            profit_cap = check_profit_cap(state.daily_pnl_pct)
            if not profit_cap.allowed:
                return RiskApproval(False, profit_cap.reason)

            panic = check_panic_mode(side=side)
            if not panic.allowed:
                return RiskApproval(False, panic.reason)

            adx_gate = check_adx_filter(symbol)
            if not adx_gate.allowed:
                return RiskApproval(False, adx_gate.reason)

            micro = run_micro_simulation(symbol, side=side)
            if not micro.allowed:
                return RiskApproval(False, micro.reason)
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.warning("بوابات مؤسسية إضافية فشلت — متابعة: %s", exc)

        # —— v1.1.2 Pre-Execution Gate + ATR لحظي من data/ ——
        try:
            from audit.execution_events import log_execution_event
            from risk.emergency_protocols import fetch_live_atr
            from risk.pre_execution_gate import validate_pre_execution

            live_atr = fetch_live_atr(symbol)
            gate = validate_pre_execution(
                symbol=symbol,
                entry_price=entry_price,
                side=side,
                stop_loss=stop_loss,
                take_profit=take_profit,
                atr_value=live_atr,
            )
            if not gate.approved:
                log_execution_event(
                    "entry_rejected",
                    symbol=symbol,
                    reason=gate.reason,
                    details={
                        "entry": entry_price,
                        "sl": stop_loss,
                        "tp": take_profit,
                        "atr": gate.atr_value,
                    },
                )
                return RiskApproval(False, gate.reason)
            stop_loss, take_profit = gate.stop_loss, gate.take_profit
            if gate.used_emergency_atr:
                log_execution_event(
                    "emergency_atr_sl",
                    symbol=symbol,
                    reason=gate.reason,
                    details={"sl": stop_loss, "tp": take_profit, "atr": gate.atr_value},
                )
        except Exception as exc:  # noqa: BLE001 — لا تكسر حلقة التشغيل
            try:
                from audit.execution_events import log_execution_event

                log_execution_event(
                    "gate_error",
                    symbol=symbol,
                    reason=str(exc),
                )
            except Exception:
                pass
            return RiskApproval(False, f"Pre-Execution Gate خطأ — رفض آمن: {exc}")

        risk_note = (
            f"مخاطرة {effective_risk_pct(risk_pct):.1f}% | "
            f"MC {mc.win_rate:.0%}{' (تجربة)' if settings.trial_mode else ''} | "
            f"scale {scale:.1f}x"
        )
        if hc_mode:
            risk_note = f"HC | {risk_note}"
        if inspection.active:
            risk_note = f"{inspection.reason} | {risk_note}"

        return RiskApproval(
            approved=True,
            reason=risk_note,
            amount=amount,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def record_closed_trade(self, pnl: float) -> None:
        if self._state is None:
            return
        self._state.record_trade(pnl)
        settings = get_settings()
        self._state.post_trade_cooldown_until = compute_post_trade_cooldown_until(
            minutes=settings.post_trade_cooldown_minutes,
        )

        streak = check_loss_streak(
            self._state.consecutive_losses,
            self._state.cooldown_until,
        )
        if streak.in_cooldown and streak.cooldown_until:
            self._state.cooldown_until = streak.cooldown_until

        kill = check_kill_switch(self._state.daily_pnl_pct)
        if kill.triggered:
            self._state.kill_switch_active = True
        self._persist()

    def check_safety_gates(self) -> RiskApproval:
        """Kill Zones + فلتر الأخبار — طبقة الأمان العامة."""
        settings = get_settings()
        zones = check_kill_zones(
            enabled=settings.kill_zones_enabled,
            allowed_sessions=settings.kill_zones_sessions,
        )
        if not zones.allowed:
            return RiskApproval(False, zones.reason)

        news = check_news_filter(blackout_minutes=settings.news_blackout_minutes)
        if not news.trading_allowed:
            return RiskApproval(False, f"أخبار: {news.reason}")
        return RiskApproval(True, "أمان: مسموح")

    def check_control_gates(self, balance: float | None = None) -> RiskApproval:
        """سقف الساعة + تهدئة ما بعد الصفقة — تُطبَّق دائماً على الدخول التلقائي."""
        bal = balance if balance is not None else (
            self._state.current_balance if self._state is not None else 0.0
        )
        if bal <= 0 and self._state is None:
            return RiskApproval(True, "لا حالة مخاطر بعد")
        state = self.ensure_state(max(bal, 1.0))
        settings = get_settings()

        post_cd = check_post_trade_cooldown(state.post_trade_cooldown_until)
        if post_cd.in_cooldown:
            return RiskApproval(False, post_cd.reason)

        state.trade_open_timestamps = prune_open_timestamps(state.trade_open_timestamps)
        rate = check_rate_limit(
            state.trade_open_timestamps,
            max_per_hour=settings.max_trades_per_hour,
        )
        if not rate.allowed:
            return RiskApproval(False, rate.reason)

        safety = self.check_safety_gates()
        if not safety.approved:
            return RiskApproval(False, safety.reason)

        return RiskApproval(True, "سيطرة+أمان: مسموح")

    def record_trade_opened(self) -> None:
        """تسجيل فتح صفقة — لسقف الساعة."""
        if self._state is None:
            return
        self._state.trade_open_timestamps = prune_open_timestamps(
            self._state.trade_open_timestamps
        )
        self._state.record_trade_open()
        self._persist()

    def record_hc_trade_open(self) -> None:
        if self._state is None:
            return
        self._state.hc_daily_trades += 1
        self._state.hc_last_trade_at = datetime.now(timezone.utc)
        self._persist()

    def record_hc_trade_close(self, pnl: float, *, was_hc: bool) -> None:
        if self._state is None or not was_hc:
            return
        if pnl >= 0:
            self._state.hc_consecutive_wins += 1
        else:
            self._state.hc_consecutive_wins = 0
        self._persist()
