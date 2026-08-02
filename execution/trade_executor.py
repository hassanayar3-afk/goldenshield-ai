"""منسق التنفيذ الرئيسي."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from config.settings import get_settings
from core.analyzer import AnalysisResult
from core.constants import meets_signal_minimum
from core.exceptions import ExecutionError
from core.technical.timeframe_aligner import TrendDirection
from data.exchange_client import get_exchange
from execution.breakeven_logic import BreakevenAction, evaluate_breakeven
from execution.slippage_guard import check_slippage
from execution.trailing_stop import evaluate_trailing_stop
from execution.correlation_filter import CorrelationFilter
from execution.dark_pool_splitter import split_order
from execution.emergency_flat import emergency_flat
from execution.models.order import OrderSide
from execution.models.trade import ExecutionResult, Position
from execution.mutex_guard import MutexGuard
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager
from operations.trade_prefs import TradePrefs
from risk.protocol_models import RISK_MODE_HIGH_CONVICTION, ProtocolApproval
from risk.risk_orchestrator import RiskOrchestrator

if TYPE_CHECKING:
    from audit.audit_trail import AuditTrail
    from audit.consensus_gate import ConsensusResult
    from audit.models.snapshot import MarketSnapshot
    from database.repositories.trade_repo import TradeRepository
    from operations.alert_dispatcher import AlertDispatcher

logger = logging.getLogger(__name__)


class TradeExecutor:
    def __init__(
        self,
        *,
        order_manager: OrderManager | None = None,
        position_manager: PositionManager | None = None,
        mutex_guard: MutexGuard | None = None,
        correlation_filter: CorrelationFilter | None = None,
        risk_orchestrator: RiskOrchestrator | None = None,
        audit_trail: AuditTrail | None = None,
        trade_repository: TradeRepository | None = None,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.order_manager = order_manager or OrderManager()
        self.position_manager = position_manager or PositionManager()
        self.mutex = mutex_guard or MutexGuard()
        self.correlation = correlation_filter or CorrelationFilter()
        self.risk = risk_orchestrator or RiskOrchestrator()
        self.audit = audit_trail
        self.trade_repo = trade_repository
        self.alerts = alert_dispatcher
        self._balance_cache: float | None = None
        self._balance_cache_at: float = 0.0

    def get_account_balance(self) -> float:
        import time

        settings = get_settings()
        now = time.monotonic()
        if self._balance_cache is not None and (now - self._balance_cache_at) < 15.0:
            return self._balance_cache

        if settings.execution_mode != "live":
            self._balance_cache = settings.paper_account_balance
            self._balance_cache_at = now
            return self._balance_cache

        from config.runtime_profile import resolve_runtime_profile

        if resolve_runtime_profile(settings).uses_mt5:
            try:
                from execution.mt5_bridge import get_mt5_bridge

                bal = float(get_mt5_bridge().account_balance())
                self._balance_cache = bal
                self._balance_cache_at = now
                return bal
            except Exception:
                logger.exception("فشل رصيد MT5 — استخدام رصيد paper")
                return settings.paper_account_balance

        if not settings.binance_api_key or not settings.binance_api_secret:
            return settings.paper_account_balance

        try:
            exchange = get_exchange()
            balance = exchange.fetch_balance()
            usdt = balance.get("USDT") or balance.get("total", {}).get("USDT")
            if isinstance(usdt, dict):
                bal = float(usdt.get("free", settings.paper_account_balance))
            else:
                bal = float(usdt or settings.paper_account_balance)
            self._balance_cache = bal
            self._balance_cache_at = now
            return bal
        except Exception:
            logger.exception("فشل جلب الرصيد — استخدام رصيد paper")
            return settings.paper_account_balance

    def _fit_amount_to_spot_balance(
        self,
        *,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> tuple[float, str]:
        """يحدّ الحجم حسب الرصيد الحر على Binance Spot — يمنع insufficient balance."""
        try:
            settings = get_settings()
            if settings.execution_mode != "live" and not bool(
                getattr(settings, "binance_demo_trading", False)
            ):
                return max(float(amount or 0.0), 0.0), ""

            exchange = get_exchange()
            bal = exchange.fetch_balance() or {}
            side_l = (side or "buy").lower()
            amt = float(amount or 0.0)
            px = float(price or 0.0)
            if px <= 0:
                return 0.0, "سعر غير صالح"

            if side_l == "buy":
                usdt = bal.get("USDT") or {}
                free_usdt = float(
                    usdt.get("free") if isinstance(usdt, dict) else (usdt or 0.0)
                )
                if free_usdt < 5.0:
                    return (
                        0.0,
                        f"رصيد USDT الحر غير كافٍ للشراء ({free_usdt:.2f}$). "
                        "أغلق جزءاً من المراكز أو أودع USDT في Demo.",
                    )
                max_amt = (free_usdt * 0.95) / px
                try:
                    max_amt = float(exchange.amount_to_precision(symbol, max_amt))
                except Exception:
                    pass
                if max_amt <= 0:
                    return (
                        0.0,
                        f"لا يمكن شراء {symbol} بالرصيد الحالي ({free_usdt:.2f} USDT)",
                    )
                # لا نستخدم كامل الرصيد عند غياب الحجم — نحدّ بـ ~2% مخاطرة تقريبية
                if amt <= 0:
                    amt = (free_usdt * 0.02) / px
                final = min(amt, max_amt)
                if final <= 0:
                    return 0.0, "حجم الشراء صفر بعد ضبط الرصيد"
                if final * px < 5.0:
                    return (
                        0.0,
                        f"قيمة الصفقة صغيرة جداً (~{final * px:.2f}$). "
                        f"USDT المتاح: {free_usdt:.2f}",
                    )
                return final, ""

            # بيع Spot: من رصيد الأصل فقط (ليس شورت)
            base = symbol.split("/", 1)[0].upper()
            asset = bal.get(base) or {}
            free_base = float(
                asset.get("free") if isinstance(asset, dict) else (asset or 0.0)
            )
            if free_base <= 0:
                return (
                    0.0,
                    f"لا يوجد رصيد {base} للبيع على Spot. "
                    "إشارة البيع تحتاج أن تملك الأصل أولاً.",
                )
            try:
                free_base = float(
                    exchange.amount_to_precision(symbol, free_base * 0.995)
                )
            except Exception:
                free_base = free_base * 0.995
            final = min(amt, free_base) if amt > 0 else free_base
            if final <= 0:
                return 0.0, f"كمية {base} المتاحة للبيع غير كافية"
            return final, ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("_fit_amount_to_spot_balance: %s", exc)
            return max(float(amount or 0.0), 0.0), ""

    def _reject(
        self,
        symbol: str,
        reason: str,
        *,
        snapshot: MarketSnapshot | None = None,
        shadow_consensus: bool = False,
    ) -> ExecutionResult:
        if self.audit is not None and snapshot is not None:
            self.audit.log_reject(snapshot, reason, shadow_consensus=shadow_consensus)
        return ExecutionResult(
            executed=False,
            symbol=symbol,
            message="مرفوض",
            rejected=True,
            reason=reason,
        )

    def try_open(
        self,
        result: AnalysisResult,
        *,
        snapshot: MarketSnapshot | None = None,
        consensus: ConsensusResult | None = None,
        prefs: TradePrefs | None = None,
        protocol: ProtocolApproval | None = None,
        manual_force: bool = False,
    ) -> ExecutionResult:
        symbol = result.symbol
        settings = get_settings()

        if snapshot is None or consensus is None:
            if self.audit is not None and not manual_force:
                snapshot, consensus = self.audit.evaluate_entry(result)

        if not manual_force:
            if consensus is not None and not consensus.approved:
                return self._reject(
                    symbol,
                    f"Shadow: {consensus.reason}",
                    snapshot=snapshot,
                    shadow_consensus=False,
                )
            if result.halted:
                return self._reject(symbol, "market_halt", snapshot=snapshot)
            if not meets_signal_minimum(result.score):
                return self._reject(symbol, f"score={result.score}", snapshot=snapshot)
            control = self.risk.check_control_gates(self.get_account_balance())
            if not control.approved:
                return self._reject(symbol, control.reason, snapshot=snapshot)

        # فرض إشارة شراء/بيع — خاصة للإجباري
        if result.signal not in {"BUY SIGNAL", "SELL SIGNAL"} or not result.passed:
            coerced = self._coerce_entry_signal(
                result, allow_any_score=manual_force
            )
            if coerced is None:
                if manual_force:
                    coerced = replace(
                        result,
                        signal="BUY SIGNAL",
                        passed=True,
                        reasons=tuple(
                            dict.fromkeys((*result.reasons, "إجباري — افتراض شراء"))
                        ),
                    )
                else:
                    return self._reject(
                        symbol,
                        f"{result.signal} — لا اتجاه واضح للدخول",
                        snapshot=snapshot,
                    )
            result = coerced

        if self.position_manager.has(symbol):
            existing = self.position_manager.get(symbol)
            # Spot: إشارة بيع على مركز شراء = إغلاق (لا شورت)
            if (
                existing is not None
                and result.signal == "SELL SIGNAL"
                and existing.side == OrderSide.BUY
            ):
                px = float(result.price or existing.entry_price or 0.0)
                closed = self.close_position(
                    symbol,
                    px,
                    reason="إشارة بيع Spot — إغلاق المركز الطويل",
                )
                if closed:
                    return ExecutionResult(
                        executed=True,
                        symbol=symbol,
                        message=f"أُغلق {symbol} عند إشارة بيع @ {px}",
                        rejected=False,
                        reason="",
                    )
                return self._reject(
                    symbol,
                    "تعذر إغلاق المركز عند إشارة البيع",
                    snapshot=snapshot,
                )
            return self._reject(symbol, "موجود مركز مفتوح على نفس الزوج", snapshot=snapshot)

        if self.position_manager.count() >= settings.max_concurrent_positions:
            return self._reject(
                symbol,
                (
                    f"الحد الأقصى للمراكز: {settings.max_concurrent_positions} "
                    f"(مفتوح {self.position_manager.count()})"
                ),
                snapshot=snapshot,
            )

        if not manual_force:
            allowed, corr_reason = self.correlation.can_open(
                symbol, self.position_manager.open_symbols()
            )
            if not allowed:
                return self._reject(symbol, corr_reason, snapshot=snapshot)

        if not self.mutex.try_acquire(symbol):
            return self._reject(symbol, "mutex_locked", snapshot=snapshot)

        try:
            return self._execute_entry(
                result,
                snapshot=snapshot,
                prefs=prefs,
                protocol=protocol,
                force_open=manual_force,
            )
        finally:
            self.mutex.release(symbol)

    def _coerce_entry_signal(
        self,
        result: AnalysisResult,
        *,
        allow_any_score: bool = False,
    ) -> AnalysisResult | None:
        """حوّل WAIT إلى BUY/SELL حسب الاتجاه. اليدوي يسمح بأي درجة."""
        if not allow_any_score and not meets_signal_minimum(result.score):
            return None
        if result.signal in {"BUY SIGNAL", "SELL SIGNAL"}:
            return replace(result, passed=True)

        direction = None
        if result.alignment is not None:
            direction = result.alignment.direction
            if direction == TrendDirection.NEUTRAL and result.alignment.per_timeframe:
                votes = list(result.alignment.per_timeframe.values())
                bull = sum(1 for d in votes if d == TrendDirection.BULLISH)
                bear = sum(1 for d in votes if d == TrendDirection.BEARISH)
                if bull > bear:
                    direction = TrendDirection.BULLISH
                elif bear > bull:
                    direction = TrendDirection.BEARISH
        if direction == TrendDirection.BULLISH:
            signal = "BUY SIGNAL"
        elif direction == TrendDirection.BEARISH:
            signal = "SELL SIGNAL"
        else:
            return None
        return replace(
            result,
            signal=signal,
            passed=True,
            reasons=tuple(dict.fromkeys((*result.reasons, "دخول حسب الاتجاه"))),
        )

    def _persist_open_trade(self, position: Position) -> None:
        if self.trade_repo is None:
            return
        from database.repositories.trade_repo import TradeRow

        self.trade_repo.save_trade(
            TradeRow(
                id=position.id,
                symbol=position.symbol,
                side=position.side.value,
                entry_price=position.entry_price,
                amount=position.amount,
                status="open",
                opened_at=position.opened_at.isoformat(),
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                is_paper=position.is_paper,
                breakeven_applied=position.breakeven_applied,
                partial_exit_done=position.partial_exit_done,
                signal_score=position.signal_score,
                risk_mode=position.risk_mode,
                exit_tier=int(getattr(position, "exit_tier", 0) or 0),
            )
        )

    def restore_open_positions(self) -> int:
        """إعادة تحميل المراكز المفتوحة من قاعدة البيانات بعد الإقلاع."""
        if self.trade_repo is None:
            return 0
        restored = 0
        for row in self.trade_repo.list_open_trades():
            if self.position_manager.has(row.symbol):
                continue
            sl = row.stop_loss if row.stop_loss is not None else row.entry_price * 0.97
            tp = row.take_profit if row.take_profit is not None else row.entry_price * 1.06
            try:
                opened_at = datetime.fromisoformat(row.opened_at)
            except ValueError:
                opened_at = datetime.now(timezone.utc)
            try:
                side = OrderSide(row.side)
            except ValueError:
                side = OrderSide.BUY
            position = Position(
                symbol=row.symbol,
                side=side,
                entry_price=row.entry_price,
                amount=row.amount,
                stop_loss=sl,
                take_profit=tp,
                id=row.id,
                opened_at=opened_at,
                breakeven_applied=row.breakeven_applied,
                partial_exit_done=row.partial_exit_done,
                is_paper=row.is_paper,
                signal_score=int(getattr(row, "signal_score", 0) or 0),
                risk_mode=str(getattr(row, "risk_mode", "standard") or "standard"),
                exit_tier=int(getattr(row, "exit_tier", 0) or 0),
            )
            self.position_manager.add(position)
            restored += 1
        if restored:
            logger.info("Restored %s open position(s) from database", restored)
        return restored

    def _persist_close_trade(self, position_id: str, exit_price: float, pnl: float) -> None:
        if self.trade_repo is None:
            return
        self.trade_repo.close_trade(position_id, exit_price=exit_price, pnl=pnl)

    def _notify_close(self, symbol: str, pnl: float, reason: str) -> None:
        if self.alerts is not None:
            self.alerts.trade_closed(symbol, pnl, reason)

    def _sync_mt5_sl_tp(
        self,
        symbol: str,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        settings = get_settings()
        if settings.execution_mode != "live" or not settings.mt5_attach_sl_tp:
            return
        from config.runtime_profile import resolve_runtime_profile

        if not resolve_runtime_profile(settings).uses_mt5:
            return
        try:
            from execution.mt5_bridge import get_mt5_bridge

            get_mt5_bridge().modify_position_sl_tp(
                symbol,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        except Exception:
            logger.exception("فشل مزامنة SL/TP مع MT5 لـ %s", symbol)

    def _execute_entry(
        self,
        result: AnalysisResult,
        *,
        snapshot: MarketSnapshot | None,
        prefs: TradePrefs | None = None,
        protocol: ProtocolApproval | None = None,
        force_open: bool = False,
    ) -> ExecutionResult:
        settings = get_settings()
        balance = self.get_account_balance()
        side_key = "sell" if result.signal == "SELL SIGNAL" else "buy"
        order_side = OrderSide.SELL if side_key == "sell" else OrderSide.BUY

        from risk.lot_calculator import LotCalculator

        amount = 0.0
        stop_loss = 0.0
        take_profit = 0.0

        if prefs is not None:
            lot_calc = LotCalculator(max(balance, 1.0))
            amount, stop_loss, take_profit = lot_calc.calculate(
                result.price,
                sl_pct=prefs.sl_pct,
                rr_ratio=prefs.rr_ratio,
                risk_pct=prefs.risk_pct,
                side=side_key,
            )
        elif force_open or settings.trial_mode:
            # لا نرفع الرصيد وهميةً إلى min_account — وإلا يُحسب حجم أكبر من المتاح
            lot_calc = LotCalculator(max(float(balance), 1.0))
            amount, stop_loss, take_profit = lot_calc.calculate(
                result.price, side=side_key
            )
            if amount <= 0 and float(balance) > 1.0 and result.price > 0:
                # حجم صغير متناسب مع الرصيد المتاح (شراء) أو سيُضبط لاحقاً للبيع
                from execution.sl_tp_calculator import calculate_sl_tp

                stop_loss, take_profit = calculate_sl_tp(
                    result.price, side=side_key
                )
                if side_key == "buy":
                    amount = max((float(balance) * 0.02) / result.price, 0.0)
                else:
                    amount = 0.0  # يُملأ من رصيد الأصل أدناه
        else:
            risk_approval = self.risk.evaluate_entry(
                result.symbol,
                result.price,
                balance,
                signal_score=result.score,
                side=side_key,
                prefs=prefs,
                protocol=protocol,
            )
            if not risk_approval.approved:
                return self._reject(
                    result.symbol,
                    risk_approval.reason,
                    snapshot=snapshot,
                )
            amount = risk_approval.amount
            stop_loss = risk_approval.stop_loss
            take_profit = risk_approval.take_profit

        # ضبط الحجم حسب الرصيد الحقيقي على Spot (سبب: insufficient balance)
        fitted, fit_reason = self._fit_amount_to_spot_balance(
            symbol=result.symbol,
            side=side_key,
            amount=float(amount or 0.0),
            price=float(result.price or 0.0),
        )
        if fitted <= 0:
            return self._reject(
                result.symbol,
                fit_reason or "رصيد غير كافٍ لتنفيذ الصفقة على Binance Spot",
                snapshot=snapshot,
            )
        amount = fitted

        if amount <= 0:
            return self._reject(result.symbol, "حجم العقد صفر", snapshot=snapshot)

        if result.price <= 0:
            return self._reject(result.symbol, "سعر غير صالح للدخول", snapshot=snapshot)

        # —— Pre-trade Max Slippage من دفتر الأوامر (v1.3) ——
        try:
            from data.orderbook_fetcher import OrderBookFetcher
            from risk.advanced_shields import check_book_slippage_pct

            book = OrderBookFetcher().fetch(result.symbol)
            best = None
            if side_key == "buy" and book.asks:
                best = float(book.asks[0].price)
            elif side_key == "sell" and book.bids:
                best = float(book.bids[0].price)
            if best is not None:
                slip_pre = check_book_slippage_pct(
                    mid_or_ref=result.price,
                    ask_or_bid=best,
                )
                if not slip_pre.allowed:
                    return self._reject(
                        result.symbol,
                        f"Max Slippage: {slip_pre.reason}",
                        snapshot=snapshot,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("pre-trade slippage skip %s: %s", result.symbol, exc)

        scaling_add_pending = False
        scaling_add_amount = 0.0
        try:
            from risk.partial_scaling import plan_partial_scaling

            plan = plan_partial_scaling(amount)
            if plan.enabled and plan.add_amount > 0:
                amount = plan.initial_amount
                scaling_add_pending = True
                scaling_add_amount = plan.add_amount
                logger.info("%s | %s", result.symbol, plan.reason)
        except Exception as exc:  # noqa: BLE001
            logger.warning("partial_scaling تخطي: %s", exc)

        # —— v1.1.2 Zero-SL Denial: بوابة أخيرة قبل إرسال الأمر للمنصة ——
        try:
            from audit.execution_events import log_execution_event
            from risk.emergency_protocols import fetch_live_atr
            from risk.pre_execution_gate import validate_pre_execution

            live_atr = fetch_live_atr(result.symbol)
            gate = validate_pre_execution(
                symbol=result.symbol,
                entry_price=result.price,
                side=side_key,
                stop_loss=stop_loss,
                take_profit=take_profit,
                atr_value=live_atr,
            )
            if not gate.approved:
                log_execution_event(
                    "entry_rejected",
                    symbol=result.symbol,
                    reason=gate.reason,
                    details={
                        "path": "trade_executor",
                        "force_open": force_open,
                        "sl": stop_loss,
                        "tp": take_profit,
                        "atr": gate.atr_value,
                    },
                )
                return self._reject(result.symbol, gate.reason, snapshot=snapshot)
            stop_loss, take_profit = gate.stop_loss, gate.take_profit
            if gate.used_emergency_atr:
                log_execution_event(
                    "emergency_atr_sl",
                    symbol=result.symbol,
                    reason=gate.reason,
                    details={"sl": stop_loss, "tp": take_profit, "atr": gate.atr_value},
                )
        except Exception as exc:  # noqa: BLE001
            try:
                from audit.execution_events import log_execution_event

                log_execution_event(
                    "gate_error",
                    symbol=result.symbol,
                    reason=str(exc),
                )
            except Exception:
                pass
            return self._reject(
                result.symbol,
                f"Pre-Execution Gate خطأ — رفض آمن: {exc}",
                snapshot=snapshot,
            )

        chunks = split_order(amount, result.price)
        # إجباري: لا تقسيم — أمر واحد يقلل فشل MT5
        if force_open:
            chunks = [amount]

        filled_amount = 0.0
        last_fill = result.price

        try:
            from execution.sl_attachment_guard import ensure_fill_has_sl_or_close

            for _index, chunk in enumerate(chunks):
                # v1.1.2+: SL/TP مع كل جزء — لا أوامر عارية
                order = self.order_manager.create_market_order(
                    result.symbol,
                    order_side,
                    chunk,
                    reference_price=result.price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
                fill_px = order.fill_price or result.price
                protected = ensure_fill_has_sl_or_close(
                    self.order_manager,
                    order=order,
                    symbol=result.symbol,
                    side=order_side,
                    amount=chunk,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reference_price=fill_px,
                )
                if not protected:
                    # أغلق أي حجم تراكمي سابق إن وُجد ثم ارفض
                    if filled_amount > 0:
                        try:
                            emergency_side = (
                                OrderSide.SELL
                                if order_side == OrderSide.BUY
                                else OrderSide.BUY
                            )
                            self.order_manager.create_market_order(
                                result.symbol,
                                emergency_side,
                                filled_amount,
                                reference_price=last_fill,
                                allow_without_stops=True,
                            )
                        except Exception:
                            logger.exception(
                                "فشل إغلاق الأجزاء السابقة بعد تذكرة عارية %s",
                                result.symbol,
                            )
                    try:
                        from audit.execution_events import log_execution_event

                        log_execution_event(
                            "naked_ticket_closed",
                            symbol=result.symbol,
                            reason="تذكرة بلا SL مؤكد — إغلاق وقائي",
                            details={"chunk": chunk, "filled_before": filled_amount},
                        )
                    except Exception:
                        pass
                    return self._reject(
                        result.symbol,
                        (
                            "تعذّر تثبيت وقف الخسارة على Binance Spot بعد الشراء، "
                            "فأُغلق الأمر فوراً لحماية رأس المال. "
                            "أعد المحاولة — إن تكرر راجع الرصيد/الدقة أو سجلات البوت."
                        ),
                        snapshot=snapshot,
                    )
                filled_amount += order.amount
                last_fill = fill_px
        except ExecutionError as exc:
            msg = str(exc)
            if "10027" in msg or "AutoTrading" in msg:
                msg = (
                    "MT5: التداول الآلي مطفي (10027). "
                    "افتح XM MT5 → اضغط Algo Trading حتى يصير أخضر ثم أعد المحاولة."
                )
            return self._reject(result.symbol, msg, snapshot=snapshot)

        # Slippage Monitor بعد التنفيذ
        max_slip_pct = float(getattr(settings, "max_slippage_pct", 0.05))
        max_slip_points = max(result.price * (max_slip_pct / 100.0), 1e-8)
        slip = check_slippage(
            requested_price=result.price,
            available_price=last_fill,
            max_slippage_points=max_slip_points,
        )
        if not slip.allowed and filled_amount > 0:
            # إغلاق فوري + رفض تسجيل دخول نظيف
            try:
                emergency_side = (
                    OrderSide.SELL if order_side == OrderSide.BUY else OrderSide.BUY
                )
                self.order_manager.create_market_order(
                    result.symbol,
                    emergency_side,
                    filled_amount,
                    reference_price=last_fill,
                    allow_without_stops=True,
                )
            except Exception:
                logger.exception("فشل إغلاق طارئ بعد انزلاق %s", result.symbol)
            return self._reject(
                result.symbol,
                f"Slippage Monitor: {slip.reason}",
                snapshot=snapshot,
            )

        risk_mode = (
            protocol.risk_mode
            if protocol is not None and protocol.approved
            else "standard"
        )
        position = Position(
            symbol=result.symbol,
            side=order_side,
            entry_price=last_fill,
            amount=round(filled_amount, 8),
            stop_loss=stop_loss,
            take_profit=take_profit,
            is_paper=settings.execution_mode != "live",
            signal_score=int(result.score),
            risk_mode=risk_mode,
            scaling_add_pending=scaling_add_pending,
            scaling_add_amount=scaling_add_amount,
            entry_filters=str(getattr(result, "reasons", "") or risk_mode),
        )
        self.position_manager.add(position)
        self._persist_open_trade(position)
        self.risk.record_trade_opened()
        if risk_mode == RISK_MODE_HIGH_CONVICTION:
            self.risk.record_hc_trade_open()

        if settings.trial_mode:
            from operations.trial_journal import log_trade_open

            log_trade_open(
                symbol=position.symbol,
                position_id=position.id,
                entry_price=position.entry_price,
                amount=position.amount,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                score=result.score,
                mode="LIVE" if settings.execution_mode == "live" else "PAPER",
            )

        if self.audit is not None and snapshot is not None:
            self.audit.log_entry(
                snapshot,
                position_id=position.id,
                reason="Shadow consensus + risk approved",
            )

        mode_label = "PAPER" if settings.execution_mode != "live" else "LIVE"
        side_label = "بيع" if order_side == OrderSide.SELL else "شراء"
        return ExecutionResult(
            executed=True,
            symbol=result.symbol,
            position_id=position.id,
            message=(
                f"[{mode_label}] {side_label} {position.amount} @ {position.entry_price:.2f}\n"
                f"SL: {position.stop_loss:.2f} | TP: {position.take_profit:.2f}"
            ),
        )

    def close_position(self, symbol: str, price: float, reason: str = "Manual Close") -> bool:
        position = self.position_manager.get(symbol)
        if position is None:
            return False
        self._close_position(position, price, reason)
        return True

    def close_position_partial(
        self,
        symbol: str,
        price: float,
        fraction: float,
        *,
        reason: str = "Partial Close",
    ) -> bool:
        position = self.position_manager.get(symbol)
        if position is None or fraction <= 0:
            return False

        amount = round(position.amount * fraction, 8)
        if amount <= 0:
            return False

        if position.side == OrderSide.BUY:
            pnl = (price - position.entry_price) * amount
            exit_side = OrderSide.SELL
        else:
            pnl = (position.entry_price - price) * amount
            exit_side = OrderSide.BUY

        self.order_manager.create_market_order(
            position.symbol,
            exit_side,
            amount,
            reference_price=price,
            allow_without_stops=True,
        )
        self.position_manager.reduce_amount(symbol, amount)
        self.risk.record_closed_trade(pnl)
        self._notify_close(position.symbol, pnl, reason)
        if self.audit is not None:
            self.audit.log_exit(position.symbol, reason=reason, pnl=pnl, position_id=position.id)
        return True

    def apply_breakeven(self, symbol: str) -> bool:
        position = self.position_manager.get(symbol)
        if position is None:
            return False
        updated = self.position_manager.update_stop_loss(symbol, position.entry_price)
        if updated is not None:
            self._persist_open_trade(updated)
            self._sync_mt5_sl_tp(symbol, stop_loss=updated.stop_loss)
        return True

    def adjust_position_sl(self, symbol: str, sl_pct: float) -> bool:
        position = self.position_manager.get(symbol)
        if position is None:
            return False
        from execution.sl_tp_calculator import calculate_sl_tp

        side = "buy" if position.side == OrderSide.BUY else "sell"
        stop_loss, _ = calculate_sl_tp(position.entry_price, sl_pct=sl_pct, side=side)
        updated = self.position_manager.update_stop_loss(symbol, stop_loss)
        if updated is not None:
            self._persist_open_trade(updated)
            self._sync_mt5_sl_tp(symbol, stop_loss=updated.stop_loss)
        return True

    def adjust_position_tp(self, symbol: str, rr_ratio: float) -> bool:
        position = self.position_manager.get(symbol)
        if position is None:
            return False
        from execution.sl_tp_calculator import calculate_sl_tp

        side = "buy" if position.side == OrderSide.BUY else "sell"
        sl_pct = abs(position.entry_price - position.stop_loss) / position.entry_price
        _, take_profit = calculate_sl_tp(
            position.entry_price,
            sl_pct=sl_pct,
            rr_ratio=rr_ratio,
            side=side,
        )
        updated = self.position_manager.update_take_profit(symbol, take_profit)
        if updated is not None:
            self._persist_open_trade(updated)
            self._sync_mt5_sl_tp(symbol, take_profit=updated.take_profit)
        return True

    def manage_positions(self, prices: dict[str, float]) -> list[BreakevenAction]:
        actions: list[BreakevenAction] = []

        for position in list(self.position_manager.all()):
            current = prices.get(position.symbol)
            if current is None or current <= 0:
                continue

            if position.side == OrderSide.BUY:
                hit_sl = current <= position.stop_loss
                hit_tp = current >= position.take_profit
            else:
                hit_sl = current >= position.stop_loss
                hit_tp = current <= position.take_profit

            if hit_sl:
                self._close_position(position, current, "Stop Loss")
                continue

            if hit_tp:
                self._close_position(position, current, "Take Profit")
                continue

            # —— Partial Scaling: إضافة الجزء الثاني عند تحقق الشرط ——
            try:
                if getattr(position, "scaling_add_pending", False) and getattr(
                    position, "scaling_add_amount", 0.0
                ) > 0:
                    from risk.partial_scaling import should_add_scaling

                    side_txt = "buy" if position.side == OrderSide.BUY else "sell"
                    ok_add, add_reason = should_add_scaling(
                        side=side_txt,
                        entry_price=position.entry_price,
                        current_price=current,
                        stop_loss=position.stop_loss,
                    )
                    if ok_add:
                        add_amt = float(position.scaling_add_amount)
                        self.order_manager.create_market_order(
                            position.symbol,
                            position.side,
                            add_amt,
                            reference_price=current,
                            stop_loss=position.stop_loss,
                            take_profit=position.take_profit,
                        )
                        position.amount = round(position.amount + add_amt, 8)
                        position.scaling_add_pending = False
                        position.scaling_add_amount = 0.0
                        self._persist_open_trade(position)
                        logger.info("Partial Scaling add: %s | %s", position.symbol, add_reason)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Partial Scaling add فشل %s: %s", position.symbol, exc)

            # —— v1.3 Smart Exits (Multi-Tier + Structural Trail) ——
            try:
                from execution.smart_exits import (
                    evaluate_multi_tier_tp,
                    structural_trail_sl,
                )

                # خروج استباقي اختياري (default off)
                try:
                    from execution.momentum_preemptive_exit import (
                        evaluate_momentum_preemptive_exit,
                    )

                    mom = evaluate_momentum_preemptive_exit(position, current)
                    if mom.should_exit:
                        self._close_position(position, current, mom.reason)
                        continue
                except Exception as mom_exc:  # noqa: BLE001
                    logger.debug("momentum preemptive: %s", mom_exc)

                smart = evaluate_multi_tier_tp(position, current)
                if smart.partial_exit_amount > 0 or smart.new_stop_loss is not None:
                    if smart.new_stop_loss is not None and smart.mark_breakeven:
                        updated = self.position_manager.update_stop_loss(
                            position.symbol, smart.new_stop_loss
                        )
                        if updated is not None:
                            updated.breakeven_applied = True
                            self._persist_open_trade(updated)
                            self._sync_mt5_sl_tp(
                                position.symbol, stop_loss=updated.stop_loss
                            )
                            position = updated
                    if smart.partial_exit_amount > 0:
                        exit_side = (
                            OrderSide.SELL
                            if position.side == OrderSide.BUY
                            else OrderSide.BUY
                        )
                        self.order_manager.create_market_order(
                            position.symbol,
                            exit_side,
                            smart.partial_exit_amount,
                            reference_price=current,
                            allow_without_stops=True,
                        )
                        updated = self.position_manager.reduce_amount(
                            position.symbol, smart.partial_exit_amount
                        )
                        if updated is not None:
                            if smart.next_exit_tier is not None:
                                updated.exit_tier = int(smart.next_exit_tier)
                            updated.partial_exit_done = True
                            if smart.mark_breakeven:
                                updated.breakeven_applied = True
                            self._persist_open_trade(updated)
                            position = updated
                    actions.append(
                        BreakevenAction(
                            move_sl_to_breakeven=smart.mark_breakeven,
                            partial_exit_amount=smart.partial_exit_amount,
                            new_stop_loss=smart.new_stop_loss,
                            mark_partial_exit=smart.partial_exit_amount > 0,
                            reason=smart.reason,
                        )
                    )
                    trail_sl = structural_trail_sl(position, current)
                    if trail_sl is not None:
                        updated = self.position_manager.update_stop_loss(
                            position.symbol, trail_sl
                        )
                        if updated is not None:
                            self._persist_open_trade(updated)
                            self._sync_mt5_sl_tp(
                                position.symbol, stop_loss=updated.stop_loss
                            )
                    continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("smart_exits فشل %s: %s", position.symbol, exc)

            # —— Emergency De-Risk تحت الضغط ——
            try:
                from risk.advanced_shields import evaluate_emergency_derisk

                risk_u = position.risk_per_unit
                if risk_u > 0:
                    if position.side == OrderSide.BUY:
                        unreal_r = (current - position.entry_price) / risk_u
                    else:
                        unreal_r = (position.entry_price - current) / risk_u
                    derisk = evaluate_emergency_derisk(unrealized_r=unreal_r)
                    if derisk.should_reduce:
                        self.close_position_partial(
                            position.symbol,
                            current,
                            derisk.close_fraction,
                            reason=derisk.reason,
                        )
                        continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("emergency derisk فشل %s: %s", position.symbol, exc)

            # عند تفعيل Multi-Tier نتجاوز Breakeven الأحادي لتجنب إغلاق مزدوج
            try:
                inst = getattr(get_settings(), "institutional_v13", {}) or {}
                if bool(inst.get("multi_tier_tp_enabled", True)):
                    trail_only = None
                    try:
                        from execution.smart_exits import structural_trail_sl

                        trail_only = structural_trail_sl(position, current)
                    except Exception:
                        trail_only = None
                    if trail_only is not None:
                        updated = self.position_manager.update_stop_loss(
                            position.symbol, trail_only
                        )
                        if updated is not None:
                            self._persist_open_trade(updated)
                            self._sync_mt5_sl_tp(
                                position.symbol, stop_loss=updated.stop_loss
                            )
                    continue
            except Exception:
                pass

            action = evaluate_breakeven(position, current)
            trailed = evaluate_trailing_stop(position, current)

            if (
                not action.move_sl_to_breakeven
                and action.partial_exit_amount <= 0
                and trailed.new_stop_loss is None
            ):
                continue

            if action.move_sl_to_breakeven and action.new_stop_loss is not None:
                updated = self.position_manager.update_stop_loss(
                    position.symbol, action.new_stop_loss
                )
                if updated is not None:
                    updated.breakeven_applied = True
                    self._persist_open_trade(updated)
                    self._sync_mt5_sl_tp(position.symbol, stop_loss=updated.stop_loss)
                    position = updated

            if action.partial_exit_amount > 0 and not position.partial_exit_done:
                exit_side = (
                    OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
                )
                self.order_manager.create_market_order(
                    position.symbol,
                    exit_side,
                    action.partial_exit_amount,
                    reference_price=current,
                    allow_without_stops=True,
                )
                updated = self.position_manager.reduce_amount(
                    position.symbol, action.partial_exit_amount
                )
                if updated is not None:
                    updated.partial_exit_done = True
                    if action.move_sl_to_breakeven:
                        updated.breakeven_applied = True
                    self._persist_open_trade(updated)
                    position = updated

            if trailed.new_stop_loss is not None:
                updated = self.position_manager.update_stop_loss(
                    position.symbol, trailed.new_stop_loss
                )
                if updated is not None:
                    self._persist_open_trade(updated)
                    self._sync_mt5_sl_tp(position.symbol, stop_loss=updated.stop_loss)
                    action = BreakevenAction(
                        move_sl_to_breakeven=False,
                        partial_exit_amount=0.0,
                        new_stop_loss=trailed.new_stop_loss,
                        mark_partial_exit=False,
                        reason=trailed.reason,
                    )

            actions.append(action)

        return actions

    def _spot_base_is_flat(self, symbol: str) -> bool:
        """True إذا لم يعد هناك رصيد للأصل على Spot (صفقة أُغلقت خارج التسجيل)."""
        try:
            settings = get_settings()
            if settings.execution_mode != "live" and not bool(
                getattr(settings, "binance_demo_trading", False)
            ):
                return False
            exchange = get_exchange()
            bal = exchange.fetch_balance() or {}
            base = symbol.split("/", 1)[0].upper()
            asset = bal.get(base) or {}
            total = float(
                asset.get("total") if isinstance(asset, dict) else (asset or 0.0)
            )
            dust = {
                "BTC": 1e-6,
                "ETH": 1e-5,
                "BNB": 1e-4,
                "SOL": 1e-3,
                "ADA": 1.0,
                "XRP": 1.0,
                "LTC": 1e-3,
                "AVAX": 0.01,
            }.get(base, 0.01)
            return total <= dust
        except Exception as exc:  # noqa: BLE001
            logger.debug("_spot_base_is_flat %s: %s", symbol, exc)
            return False

    def _close_position(self, position: Position, price: float, reason: str) -> None:
        if position.side == OrderSide.BUY:
            pnl = (price - position.entry_price) * position.amount
            exit_side = OrderSide.SELL
        else:
            pnl = (position.entry_price - price) * position.amount
            exit_side = OrderSide.BUY

        order_ok = False
        try:
            self.order_manager.create_market_order(
                position.symbol,
                exit_side,
                position.amount,
                reference_price=price,
                allow_without_stops=True,
            )
            order_ok = True
        except Exception as exc:  # noqa: BLE001
            # إن كان الرصيد على المنصة صفراً فالصفقات أُغلقت فعلياً دون تسجيل
            already_flat = self._spot_base_is_flat(position.symbol)
            if already_flat:
                logger.warning(
                    "إغلاق %s: الأمر فشل لكن الرصيد صفر على المنصة — تسجيل الإغلاق | %s",
                    position.symbol,
                    exc,
                )
                order_ok = True
            else:
                logger.exception("فشل أمر إغلاق %s: %s", position.symbol, exc)
                raise

        if not order_ok:
            return

        self.position_manager.remove(position.symbol)
        self.risk.record_closed_trade(pnl)
        self.risk.record_hc_trade_close(
            pnl,
            was_hc=position.risk_mode == RISK_MODE_HIGH_CONVICTION,
        )
        self._persist_close_trade(position.id, price, pnl)
        self._notify_close(position.symbol, pnl, reason)

        # —— صندوق أسود للخسائر (طبقة مضافة) ——
        try:
            if pnl < 0:
                from intelligence.black_box_logger import record_losing_trade_blackbox

                side_txt = "buy" if position.side == OrderSide.BUY else "sell"
                record_losing_trade_blackbox(
                    symbol=position.symbol,
                    side=side_txt,
                    entry_price=float(position.entry_price),
                    exit_price=float(price),
                    pnl=float(pnl),
                    reason=reason,
                    indicators={
                        "signal_score": int(getattr(position, "signal_score", 0) or 0),
                        "filters": str(getattr(position, "entry_filters", "") or ""),
                    },
                    alerts=self.alerts,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("blackbox on close: %s", exc)

        try:
            from operations.smart_trade_report import (
                format_smart_trade_report,
                maybe_send_smart_report,
            )

            report = format_smart_trade_report(
                symbol=position.symbol,
                side=str(position.side),
                entry_price=position.entry_price,
                exit_price=price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                pnl=pnl,
                reason=reason,
                signal_score=int(getattr(position, "signal_score", 0) or 0),
                filters=str(getattr(position, "entry_filters", "") or ""),
            )
            maybe_send_smart_report(self.alerts, report)
        except Exception as exc:  # noqa: BLE001
            logger.warning("smart trade report تخطي: %s", exc)

        if pnl < 0:
            try:
                from operations.loss_trade_report import (
                    format_losing_trade_report_telegram,
                    record_losing_trade_from_position,
                )

                loss_report = record_losing_trade_from_position(
                    position,
                    exit_price=price,
                    pnl=pnl,
                    reason=reason,
                )
                if loss_report is not None and self.alerts is not None:
                    telegram = getattr(self.alerts, "telegram", None)
                    if telegram is not None:
                        telegram.send_message(
                            format_losing_trade_report_telegram(loss_report)
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("losing trade report تخطي: %s", exc)

        settings = get_settings()
        if settings.trial_mode:
            from operations.trial_journal import log_trade_close

            log_trade_close(
                symbol=position.symbol,
                position_id=position.id,
                exit_price=price,
                pnl=pnl,
                reason=reason,
            )

        if self.audit is not None:
            self.audit.log_exit(
                position.symbol,
                reason=reason,
                pnl=pnl,
                position_id=position.id,
            )
        logger.info("إغلاق %s — %s @ %.2f (PnL: %.2f)", position.symbol, reason, price, pnl)

    def emergency_close_all(self, prices: dict[str, float] | None = None) -> list[str]:
        results = emergency_flat(
            self.order_manager,
            self.position_manager,
            prices=prices,
        )
        price_map = prices or {}
        for item in results:
            self.risk.record_closed_trade(item.pnl)
            exit_price = price_map.get(item.symbol, 0.0)
            self._persist_close_trade(item.position_id, exit_price, item.pnl)
            self._notify_close(item.symbol, item.pnl, "Emergency Flat")
            if self.audit is not None:
                self.audit.log_exit(
                    item.symbol,
                    reason="Emergency Flat",
                    pnl=item.pnl,
                    position_id=item.position_id,
                )
            if item.pnl < 0:
                try:
                    from operations.loss_trade_report import (
                        build_losing_trade_report,
                        format_losing_trade_report_telegram,
                        save_losing_trade_report,
                    )

                    loss_report = build_losing_trade_report(
                        symbol=item.symbol,
                        side="unknown",
                        entry_price=0.0,
                        exit_price=float(exit_price),
                        amount=0.0,
                        pnl=float(item.pnl),
                        stop_loss=0.0,
                        take_profit=0.0,
                        exit_reason="Emergency Flat",
                        position_id=str(item.position_id),
                        extra={"source": "emergency_flat"},
                    )
                    save_losing_trade_report(loss_report)
                    if self.alerts is not None:
                        telegram = getattr(self.alerts, "telegram", None)
                        if telegram is not None:
                            telegram.send_message(
                                format_losing_trade_report_telegram(loss_report)
                            )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("emergency losing report تخطي: %s", exc)
        return [item.symbol for item in results]
