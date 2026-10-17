import asyncio
import logging
import os
import sys
from pathlib import Path

# Windows: avoid OSError on emoji/Arabic print when stdout is redirected
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _force_official_workdir() -> None:
    """ثبّت مجلد العمل على المسار الرسمي قبل أي إعدادات/DB."""
    try:
        raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
        root = Path(raw)
        if root.is_dir():
            os.chdir(root)
            os.environ["GOLDENSHIELD_OFFICIAL_ROOT"] = str(root)
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
    except Exception:
        pass


_force_official_workdir()

from audit.audit_trail import AuditTrail
from audit.decision_logger import DecisionLogger
from audit.snapshot_recorder import SnapshotRecorder
from core.constants import is_auto_entry_allowed, score_to_percent
from core.analyzer import MarketAnalyzer
from config.settings import get_settings
from config.runtime_profile import resolve_runtime_profile
from core.market_halt import check_market_halt
from data.connection_monitor import ConnectionMonitor
from data.ticker_fetcher import TickerFetcher
from database.backup_manager import BackupManager, BackupScheduler
from database.connection import init_database
from database.gdrive_uploader import upload_backup
from database.telegram_backup import upload_backup_to_telegram
from database.repositories.config_repo import ConfigRepository
from database.repositories.operations_repo import OperationsRepository
from database.repositories.snapshot_repo import SnapshotRepository
from database.repositories.trade_repo import TradeRepository
from execution.trade_executor import TradeExecutor
from operations.alert_dispatcher import AlertDispatcher
from operations.api_watchdog import ApiWatchdog
from operations.daily_report import format_daily_report, format_daily_report_telegram
from operations.message_templates import format_cycle_signals_message, format_startup_message
from operations.error_logger import set_db_log_sink, setup_operations_logging
from operations.signal_filter import is_premium_trade_signal
from operations.panic_button import PanicButton
from operations.pre_flight_checklist import run_pre_flight
from operations.runtime_state import OperationsRuntime
from operations.symbol_registry import get_symbol_registry
from operations.shutdown_guard import clear_user_stop, is_user_stopped, should_block_signals
from operations.scheduler import DailyReportScheduler
from operations.telegram_commands import TelegramCommandHandler
from audit.execution_events import log_execution_event
from risk.emergency_protocols import run_capital_protection_watchdog
from risk.halt_policy import evaluate_trading_halt
from risk.heartbeat_guard import check_heartbeat_guard
from risk.high_conviction_protocol import evaluate_high_conviction_eligibility
from risk.risk_orchestrator import RiskOrchestrator
from risk.standard_bonus_profile import check_bonus_entry_allowed, resolve_trade_prefs

logger = logging.getLogger(__name__)

BUILD_TAG = "2026-07-29-v13-institutional"

_connection_monitor = ConnectionMonitor()
_audit = AuditTrail()
_risk = RiskOrchestrator(connection_monitor=_connection_monitor)
_executor = TradeExecutor(risk_orchestrator=_risk, audit_trail=_audit)
_ticker_fetcher = TickerFetcher()
_runtime = OperationsRuntime(
    manual_entry_required=get_settings().manual_entry_required,
)
_alerts = AlertDispatcher()
_panic = PanicButton(_executor, _alerts)
_report_scheduler = DailyReportScheduler()
_backup_scheduler = BackupScheduler()
_backup_manager: BackupManager | None = None
_operations_repo: OperationsRepository | None = None
_kill_switch_notified = False
_watchdog_cycle = 0
_watchlist_sent = False
_last_alive_pulse = 0.0
_telegram_handler: TelegramCommandHandler | None = None
_cycle_opened_trades: list[dict] = []


def _ssot_open_count() -> int:
    """عدد المراكز المفتوحة من مصدر الحقيقة الوحيد (Binance) — سياق موحّد مع اللوحة."""
    try:
        from execution.binance_position_sync import get_live_open_positions_ssot

        _, n = get_live_open_positions_ssot(_executor)
        return int(n or 0)
    except Exception:
        try:
            return int(_executor.position_manager.count())
        except Exception:
            return 0


def _log_project_rules_banner() -> None:
    """يسجّل قواعد المحادثة عند الإقلاع — مقترنة بملف التشغيل."""
    try:
        from config.project_rules import ARCHITECTURE_MODE, PROJECT_RULES_VERSION, load_project_rules

        rules = load_project_rules()
        msg = (
            f"{PROJECT_RULES_VERSION} | {ARCHITECTURE_MODE} | "
            f"HYBRID auto≥9/10 manual=7–8 "
            f"ref={rules.reference_capital:.0f} "
            f"min_trade={rules.min_trade_notional:.0f}$ "
            f"CB={rules.circuit_breaker_max_losses} "
            f"pipeline={'ON' if rules.enterprise_pipeline else 'OFF'} "
            f"BOT_FORCE_ACTIVE={os.getenv('BOT_FORCE_ACTIVE', 'true')}"
        )
        logger.info(msg)
        print(f"📐 {msg}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("project_rules banner: %s", exc)


def _init_persistence(settings) -> None:
    global _audit, _backup_manager, _operations_repo

    db = init_database(settings.db_path)
    snapshot_repo = SnapshotRepository(db)
    trade_repo = TradeRepository(db)
    config_repo = ConfigRepository(db)
    _operations_repo = OperationsRepository(db)

    from database.repositories.risk_state_repo import load_risk_state, save_risk_state

    def _persist_risk(state, session_day) -> None:
        save_risk_state(config_repo, state, session_day)

    _risk.set_persist_callback(_persist_risk)
    saved_state, saved_day = load_risk_state(config_repo)
    if saved_state is not None:
        _risk.restore_state(saved_state, saved_day)
        logger.info(
            "Restored risk state (balance=%.2f, kill=%s, losses=%s)",
            saved_state.current_balance,
            saved_state.kill_switch_active,
            saved_state.consecutive_losses,
        )

    _audit = AuditTrail(
        snapshot_recorder=SnapshotRecorder(repository=snapshot_repo),
        decision_logger=DecisionLogger(repository=trade_repo),
    )
    _executor.audit = _audit
    _executor.trade_repo = trade_repo
    _executor.alerts = _alerts
    try:
        from operations.startup_cleanup import run_startup_cleanup

        cleaned = run_startup_cleanup()
        if cleaned:
            logger.info("startup_cleanup: %s", cleaned)
    except Exception as cleanup_exc:  # noqa: BLE001
        logger.warning("startup_cleanup skipped: %s", cleanup_exc)
    restored = _executor.restore_open_positions()
    if restored:
        logger.info("Open positions restored: %s", restored)
    # مصدر الحقيقة الوحيد عند الإقلاع (نفس فلتر اللوحة/مراكزي)
    try:
        from execution.binance_position_sync import get_live_open_positions_ssot

        live_positions, live_count = get_live_open_positions_ssot(_executor)
        logger.info(
            "Startup SSoT open positions: %s (symbols=%s)",
            live_count,
            ",".join(p.symbol for p in live_positions) or "-",
        )
        if live_count:
            print(f"🔄 مرآة Binance عند الإقلاع: {live_count} مركز مفتوح")
        else:
            print("🔄 مرآة Binance عند الإقلاع: لا مراكز مفتوحة (مطابق للمنصة)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup SSoT sync: %s", exc)
        try:
            from execution.binance_position_sync import sync_binance_spot_positions

            synced = sync_binance_spot_positions(_executor)
            if synced:
                logger.info("Binance holdings synced: %s", ", ".join(synced))
                print(f"🔄 مزامنة أرصدة Binance → مراكز: {', '.join(synced)}")
        except Exception as sync_exc:  # noqa: BLE001
            logger.warning("binance position sync: %s", sync_exc)

    _backup_manager = BackupManager(settings.db_path)

    set_db_log_sink(_operations_repo.save_operation_log)
    config_repo.set("last_startup_env", settings.env)
    config_repo.set("telegram_chat_id", settings.telegram_chat_id or "")
    logger.info("Database ready: %s", settings.db_path)
    try:
        from operations.report_archive import ensure_archive_started

        started = ensure_archive_started()
        if started:
            logger.info("Daily report file archive ready: %s", started)
    except Exception as exc:  # noqa: BLE001
        logger.warning("report archive init: %s", exc)


def _fetch_prices(symbols: list[str]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for symbol in symbols:
        try:
            prices[symbol] = _ticker_fetcher.fetch(symbol).last
        except Exception as exc:
            logger.warning("فشل جلب سعر %s: %s", symbol, exc)
    return prices


def _sync_risk_session() -> None:
    balance = _executor.get_account_balance()
    _risk.ensure_state(balance)


def _emergency_flat_if_needed(reason: str, symbols: list[str]) -> None:
    if not _executor.position_manager.count():
        return
    prices = _fetch_prices(symbols)
    closed = _executor.emergency_close_all(prices)
    if closed:
        msg = f"Emergency Flat ({reason}): {', '.join(closed)}"
        print(f"🚨 {msg}")
        _alerts.emergency("Emergency Flat", msg)


def _run_open_position_management(prices: dict[str, float], *, label: str = "") -> None:
    """إدارة المراكز المفتوحة دائماً (حتى أثناء Pause/Kill) — طبقة حماية."""
    try:
        if not _executor.position_manager.count():
            return
        actions = _executor.manage_positions(prices)
        for action in actions:
            if action.reason:
                prefix = f"⚖️ [{label}] " if label else "⚖️ "
                print(f"{prefix}Breakeven/Trail: {action.reason}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("manage_positions أثناء الإيقاف فشل: %s", exc)


def _run_priority0_protection(symbols: list[str], prices: dict[str, float]) -> dict[str, float]:
    """Priority-0 Volatility Guard — لا يوقف الحلقة عند الخطأ."""
    settings = get_settings()
    try:
        if bool(getattr(settings, "emergency_protocols_enabled", True)):
            hits = run_capital_protection_watchdog(
                _executor.position_manager.all(),
                prices,
            )
            for hit in hits:
                log_execution_event(
                    "volatility_guard_close",
                    symbol=hit.symbol,
                    reason=hit.reason,
                )
                px = float(prices.get(hit.symbol) or 0.0)
                if px > 0:
                    closed = _executor.close_position(
                        hit.symbol, px, reason=hit.reason
                    )
                    if closed:
                        print(f"🛡️ Priority-0 Volatility Guard: {hit.reason}")
                        _alerts.emergency("Volatility Guard", hit.reason)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Priority-0 capital protection فشل: %s", exc)
    return prices


def _notify_kill_switch_if_needed() -> None:
    global _kill_switch_notified
    state = _risk.state
    if state and state.kill_switch_active and not _kill_switch_notified:
        _alerts.kill_switch_activated(
            f"PnL اليومي {state.daily_pnl_pct:+.2f}% — تداول موقوف"
        )
        _kill_switch_notified = True


def _maybe_send_daily_report() -> None:
    if not _report_scheduler.should_run_daily_report():
        return
    from datetime import date

    report = format_daily_report(risk=_risk, executor=_executor, audit=_audit)
    report_html = format_daily_report_telegram(risk=_risk, executor=_executor, audit=_audit)
    print(report)
    # في وضع الإشارات فقط: يبقى التقرير في السجل/قاعدة البيانات دون إزعاج تيليجرام
    if not get_settings().telegram_signals_only:
        _alerts.send_formatted(report_html, plain_log=f"[INFO] تقرير يومي\n{report}")
    else:
        from operations.error_logger import log_operation

        log_operation(f"[INFO] تقرير يومي (صامت على تيليجرام)\n{report}")
    if _operations_repo is not None:
        _operations_repo.save_daily_report(date.today().isoformat(), report)
    _report_scheduler.mark_daily_report_sent()


def _maybe_run_daily_backup() -> None:
    if _backup_manager is None or not _backup_scheduler.should_run_backup():
        return
    result = _backup_manager.create_backup()
    if result.success:
        logger.info(result.message)
        vault = upload_backup_to_telegram(result.path or "")
        if vault.uploaded:
            logger.info(vault.message)
        else:
            logger.info("Telegram Vault: %s", vault.message)
        gdrive = upload_backup(result.path or "")
        if not gdrive.uploaded:
            logger.info("GDrive: %s", gdrive.message)
    _backup_scheduler.mark_backup_done()


def _send_cycle_signals(entries: list[dict]) -> None:
    from operations.signal_filter import is_notifiable_entry

    qualified = [e for e in entries if is_notifiable_entry(e)]
    if not qualified:
        return
    msg = format_cycle_signals_message(qualified)
    plain_lines = [
        f"{entry['symbol']}: {entry['signal']} ({entry['score']}/10 @ {entry['price']:.2f})"
        for entry in qualified
    ]
    _alerts.send_formatted(msg, plain_log="[INFO] تحديث الإشارات\n" + "\n".join(plain_lines))


def _flush_opened_trades_list() -> None:
    """إرسال كل صفقات الدورة في رسالة واحدة بدل رسائل متفرقة."""
    global _cycle_opened_trades
    if not _cycle_opened_trades:
        return
    batch = list(_cycle_opened_trades)
    _cycle_opened_trades = []
    _alerts.trades_opened_batch(batch)


def _maybe_send_qualified_signals_list(
    telegram_handler: TelegramCommandHandler,
    entries: list[dict],
) -> None:
    """قائمة إشارات موحّدة بعد الدورة — بدل رسالة لكل زوج."""
    if should_block_signals() or _runtime.user_stopped:
        return
    if not telegram_handler.enabled:
        return
    telegram_handler.send_qualified_signals_list(entries)


def _maybe_send_watchlist_digest(telegram_handler: TelegramCommandHandler, entries: list[dict]) -> None:
    # أُلغي إرسال قوائم الانتظار — الإشارات فقط عبر القائمة الموحّدة الجاهزة
    return


def _maybe_send_alive_pulse(telegram_handler: TelegramCommandHandler, entries: list[dict]) -> None:
    """نبضة صحة ساعية — اتصال، ذاكرة، مراكز."""
    global _last_alive_pulse
    try:
        inst = getattr(get_settings(), "institutional_v13", {}) or {}
        if not bool(inst.get("health_heartbeat_hourly_enabled", True)):
            return
        import time
        import os

        now = time.monotonic()
        if _last_alive_pulse and (now - _last_alive_pulse) < 3600:
            return
        _last_alive_pulse = now
        if should_block_signals() or _runtime.user_stopped:
            return
        if not telegram_handler.enabled:
            return

        mem_mb = 0.0
        try:
            import psutil  # type: ignore

            mem_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except Exception:
            try:
                import resource

                mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            except Exception:
                mem_mb = 0.0

        ping_ms = "?"
        try:
            import time as _t
            from data.connection_utils import ping_exchange

            t0 = _t.perf_counter()
            ping_exchange()
            ping_ms = f"{(_t.perf_counter() - t0) * 1000:.0f}"
        except Exception:
            ping_ms = "fail"

        open_n = _ssot_open_count()
        provider = _connection_monitor.last_provider or "n/a"
        err = _connection_monitor.last_error or "لا أخطاء"
        msg = (
            "🫀 Health Check (ساعة)\n"
            f"Provider: {provider}\n"
            f"Ping: {ping_ms} ms\n"
            f"مراكز: {open_n}\n"
            f"ذاكرة≈ {mem_mb:.0f} MB\n"
            f"آخر خطأ: {err}"
        )
        if not get_settings().telegram_signals_only:
            _alerts.send_formatted(msg.replace("\n", "\n"), plain_log=f"[INFO] {msg}")
        else:
            from operations.error_logger import log_operation

            log_operation(f"[INFO] {msg}")
            # حتى في signals_only نرسل نبضة صحة خفيفة للطوارئ التشغيلية
            try:
                _alerts.send_formatted(
                    f"<b>Health</b>\nPing {ping_ms}ms | Pos {open_n} | RAM {mem_mb:.0f}MB",
                    plain_log=f"[INFO] {msg}",
                )
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("hourly health pulse failed: %s", exc)


async def check_symbol(
    symbol: str,
    *,
    commander: str | None = None,
    risk_pct: float | None = None,
    engine_proposal=None,
) -> dict | None:
    """فحص الرمز ثم محاولة التنفيذ عند تأهل الإشارة."""
    if _runtime.user_stopped or should_block_signals():
        return None
    try:
        if engine_proposal is not None:
            from core.analyzer import AnalysisResult

            result = AnalysisResult(
                symbol=engine_proposal.symbol,
                signal=engine_proposal.signal,
                price=float(engine_proposal.price),
                sma=0.0,
                score=int(engine_proposal.score),
                passed=bool(engine_proposal.passed),
                reasons=tuple(engine_proposal.reasons or ()),
            )
        else:
            analyzer = MarketAnalyzer(symbol=symbol)
            result = analyzer.analyze()

        if result.price <= 0:
            detail = result.reasons[0] if result.reasons else ""
            print(f"❌ {symbol} | فشل جلب البيانات — {detail}")
            return None

        snapshot, consensus = _audit.record_market_check(result)
        signal_label = "HALTED" if result.halted else result.signal
        balance = _executor.get_account_balance()
        side = "sell" if result.signal == "SELL SIGNAL" else "buy"
        open_count = _ssot_open_count()
        prefs = resolve_trade_prefs(symbol=symbol, signal_score=result.score)
        if risk_pct is not None and float(risk_pct) > 0:
            from operations.trade_prefs import TradePrefs

            prefs = TradePrefs(
                risk_pct=float(risk_pct),
                sl_pct=prefs.sl_pct,
                rr_ratio=prefs.rr_ratio,
            )
        hc_protocol = evaluate_high_conviction_eligibility(
            result,
            consensus=consensus,
            risk_state=_risk.state,
            open_positions=open_count,
        )
        if hc_protocol.approved and hc_protocol.trade_prefs is not None:
            prefs = hc_protocol.trade_prefs

        bonus_ok, bonus_reason = check_bonus_entry_allowed(result)
        risk_approval = _risk.evaluate_entry(
            symbol,
            result.price,
            balance,
            signal_score=result.score,
            side=side,
            prefs=prefs,
            protocol=hc_protocol,
        )
        premium = is_premium_trade_signal(
            result, consensus=consensus, risk_approval=risk_approval
        )
        entry = {
            "symbol": symbol,
            "price": result.price,
            "score": result.score,
            "signal": signal_label,
            "reasons": result.reasons,
            "premium": premium,
            "passed": bool(result.passed),
        }

        print(
            f"✅ {symbol} | السعر: {result.price:.2f} | "
            f"الدرجة: {result.score}/10 | الحالة: {result.signal}"
            + (" | ⭐ مؤهلة" if premium else "")
        )

        if result.halted:
            print(f"⏸️ {symbol} متوقف — {result.reasons[-1]}")
            _audit.log_analysis_outcome(snapshot, result)
            return entry

        # —— تبريد زوج بعد كشف فخاخ ظلّية ——
        try:
            from intelligence.shadow_stress_engine import symbol_is_cooled

            cooled, cool_reason = symbol_is_cooled(symbol)
            if cooled and result.signal in {"BUY SIGNAL", "SELL SIGNAL"}:
                print(f"🧊 {symbol}: {cool_reason}")
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                return entry
        except Exception as exc:  # noqa: BLE001
            logger.warning("symbol cooldown check: %s", exc)

        if result.signal == "REJECTED":
            print(f"⛔ {symbol} مرفوض — {result.reasons[0]}")
            _audit.log_analysis_outcome(snapshot, result)
            return entry

        settings = get_settings()
        pct = score_to_percent(result.score)
        auto_threshold = int(getattr(settings, "auto_entry_min_percent", 90) or 90)
        if commander:
            try:
                from terminal.scoring import confidence_percent, meets_elite

                pct = int(confidence_percent(result.score))
                if meets_elite(result.score):
                    from terminal.limits import load_commander_limits

                    lim = load_commander_limits()
                    auto_ok = open_count < lim.global_max
                    auto_reason = (
                        f"Elite {pct}% [{commander}] — {open_count + 1}/{lim.global_max}"
                        if auto_ok
                        else f"سقف {lim.global_max} صفقات"
                    )
                else:
                    auto_ok, auto_reason = False, f"Elite Gate {pct}%"
            except Exception as elite_exc:  # noqa: BLE001
                logger.warning("elite auto path: %s", elite_exc)
                auto_ok, auto_reason = is_auto_entry_allowed(
                    result.score, open_count, soft_min=auto_threshold
                )
        else:
            auto_ok, auto_reason = is_auto_entry_allowed(
                result.score,
                open_count,
                soft_min=auto_threshold,
            )
        trial = bool(settings.trial_mode)

        # دخول تلقائي فقط عند ≥ عتبة الضمان (افتراضي 95) + اجتياز التحليل
        ready_for_entry = (
            result.signal in {"BUY SIGNAL", "SELL SIGNAL"}
            and result.passed
            and auto_ok
        )

        if not ready_for_entry:
            if (
                result.signal in {"BUY SIGNAL", "SELL SIGNAL"}
                and result.passed
                and not auto_ok
            ):
                print(f"⏸️ {symbol}: {auto_reason}")
            _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
            return entry

        if not bonus_ok:
            print(f"⏸️ {symbol}: {bonus_reason}")
            _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
            return entry

        if hc_protocol.approved:
            print(f"🔒 {symbol}: {hc_protocol.reason}")

        if not consensus.approved:
            print(f"🚫 رفض Shadow {symbol}: {consensus.reason}")
        elif not risk_approval.approved:
            print(f"⏳ {symbol}: مخاطر — {risk_approval.reason}")
        else:
            print(f"📲 {symbol}: {pct}/100 — {auto_reason}")

        if not trial:
            if not consensus.approved:
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                return entry
            if not risk_approval.approved:
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                return entry
            if _runtime.manual_entry_required:
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                print(f"📲 {symbol}: {pct}/100 — بانتظار موافقتك من القائمة")
                return entry

        # حتى في التجربة: لا تجاوز بوابة المخاطر دون موافقة
        if trial and not risk_approval.approved:
            print(f"⏸️ تجربة {symbol}: مخاطر — {risk_approval.reason} (لا فتح بدون موافقة المخاطر)")
            _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
            return entry

        if not consensus.approved:
            _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
            return entry

        # —— لجنة مخاطر + ماكرو (طبقات مضافة) ——
        try:
            from risk.macro_flow_gate import evaluate_macro_flow_gate
            from risk.risk_committee import evaluate_risk_committee

            macro = evaluate_macro_flow_gate(side=side, symbol=symbol)
            if not macro.approved:
                print(f"🌐 {symbol}: {macro.reason}")
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                return entry
            committee = evaluate_risk_committee(
                symbol=symbol,
                side=side,
                score=int(result.score),
                signal=str(result.signal),
                reasons=tuple(result.reasons or ()),
            )
            if not committee.approved:
                print(f"🏛️ {symbol}: {committee.reason}")
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                return entry
        except Exception as exc:  # noqa: BLE001
            logger.warning("risk committee/macro gate: %s", exc)

        # —— ظل موازٍ قبل/مع التنفيذ ——
        try:
            from intelligence.shadow_stress_engine import maybe_register_shadow_hypothesis

            maybe_register_shadow_hypothesis(
                symbol=symbol,
                signal=str(result.signal),
                score=int(result.score),
                price=float(result.price),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("shadow register: %s", exc)

        # Pause/Kill: أبقِ الإشارات في الدورة، امنع الدخول التلقائي فقط
        try:
            auto_halt = evaluate_trading_halt(
                paused=_runtime.paused,
                kill_switch_active=bool(
                    _risk.state and _risk.state.kill_switch_active
                ),
            )
            if auto_halt.entries_blocked:
                print(f"⏸️ {symbol}: دخول تلقائي موقوف — {auto_halt.reason}")
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                return entry
        except Exception as exc:  # noqa: BLE001
            logger.warning("halt check before open: %s", exc)

        # —— خط أنابيب المؤسسة المتسلسل (Fail-Closed على المسار التلقائي) ——
        try:
            from config.project_rules import load_project_rules as _load_pr
            from core.enterprise_pipeline import run_pre_execution_pipeline

            if bool(_load_pr().enterprise_pipeline):
                losses = int(
                    getattr(getattr(_risk, "state", None), "consecutive_losses", 0) or 0
                )
                pipe = run_pre_execution_pipeline(
                    symbol=symbol,
                    signal=str(result.signal),
                    score=result.score,
                    price=float(result.price),
                    reasons=tuple(result.reasons or ()),
                    consecutive_losses=losses,
                    consensus_approved=bool(consensus.approved),
                    risk_approved=bool(risk_approval.approved),
                    halted=bool(result.halted),
                    for_auto_open=True,
                )
                if not pipe.approved:
                    print(f"🏛 {symbol}: Pipeline/{pipe.stage} — {pipe.reason}")
                    _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
                    return entry
        except Exception as exc:  # noqa: BLE001
            # Fail-Closed: أي استثناء حرج يمنع التنفيذ التلقائي فوراً
            logger.error("enterprise pipeline FAIL-CLOSED %s: %s", symbol, exc)
            print(f"🏛 {symbol}: Pipeline FAIL-CLOSED — {exc}")
            try:
                _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
            except Exception:  # noqa: BLE001
                pass
            return entry

        exec_result = _executor.try_open(
            result,
            snapshot=snapshot,
            consensus=consensus,
            prefs=prefs,
            protocol=hc_protocol,
            manual_force=False,
            commander=commander or "",
        )
        if exec_result.executed:
            print(f"📈 تنفيذ تلقائي ({pct}/100): {exec_result.message}")
            pos = _executor.position_manager.get(symbol)
            side_ar = "بيع" if result.signal == "SELL SIGNAL" else "شراء"
            mode = "LIVE" if get_settings().execution_mode == "live" else "PAPER"
            if pos is not None:
                _cycle_opened_trades.append(
                    {
                        "symbol": symbol,
                        "side": side_ar,
                        "amount": float(pos.amount),
                        "entry": float(pos.entry_price),
                        "sl": float(pos.stop_loss),
                        "tp": float(pos.take_profit),
                        "mode": mode,
                        "score": int(result.score),
                        "detail": exec_result.message,
                    }
                )
            else:
                _cycle_opened_trades.append(
                    {
                        "symbol": symbol,
                        "side": side_ar,
                        "mode": mode,
                        "score": int(result.score),
                        "detail": exec_result.message,
                    }
                )
            entry["premium"] = True
            entry["signal"] = result.signal
            entry["passed"] = True
        elif exec_result.rejected:
            print(f"🚫 رفض تنفيذ {symbol}: {exec_result.reason}")
        else:
            print(f"… {symbol}: جارٍ المتابعة — {exec_result.message}")

        _audit.log_analysis_outcome(snapshot, result, consensus=consensus)
        return entry

    except Exception as exc:
        logger.exception("خطأ أثناء معالجة %s", symbol)
        print(f"⚠️ خطأ أثناء معالجة {symbol}: {exc}")
        return None


def _force_bot_active(*, reason: str = "startup") -> None:
    """يمنع وضع السكون عند التشغيل: امسح الإيقاف الدائم وألغِ Pause."""
    try:
        cleared = clear_user_stop()
        _runtime.user_stopped = False
        _runtime.paused = False
        _runtime.panic_latched = False
        _runtime.resume()
        print(f"▶️ البوت نشط إجبارياً ({reason})" + (" — أُزيلت علامة الإيقاف" if cleared else ""))
    except Exception as exc:  # noqa: BLE001
        logger.warning("force_bot_active: %s", exc)


def _bot_force_active_enabled() -> bool:
    raw = (os.getenv("BOT_FORCE_ACTIVE", "true") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _loop_sleep_seconds(settings) -> int:
    try:
        from operations.console_pulse import effective_loop_seconds

        return effective_loop_seconds(getattr(settings, "loop_interval_seconds", 4))
    except Exception:
        return 4


async def run_bot() -> None:
    global _telegram_handler
    _force_official_workdir()
    # أعد تحميل الإعدادات بعد تثبيت المسار — نفس DB دائماً
    from config.settings import load_settings

    settings = load_settings(reload=True)
    setup_operations_logging(settings.log_level)
    loop_sec = _loop_sleep_seconds(settings)
    print(
        f"⚡ وضع النبض السريع | No-Sleep=ON | فاصل الدورة ~{loop_sec}s | "
        f"بث إشارات CMD/سجل لحظي"
    )
    print(f"📂 CWD={Path.cwd()} | DB={settings.db_path}")

    # عند فتح/تشغيل الملف: ممنوع البدء متوقفاً أو في سكون
    if _bot_force_active_enabled() or is_user_stopped():
        _force_bot_active(reason="startup")

    if is_user_stopped():
        print("🛑 البوت متوقف بقرارك — شغّل 00_START.bat لإعادة التشغيل.")
        sys.exit(0)

    try:
        from operations.single_instance import ensure_singleton_or_exit

        ensure_singleton_or_exit()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("single instance lock: %s", exc)

    skip_binance_ping = (
        os.getenv("PRE_FLIGHT_SKIP_BINANCE_PING", "").strip().lower() in {"1", "true", "yes", "on"}
        or os.getenv("GS_VPS_SOFT_BINANCE", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    preflight = run_pre_flight(
        connection_monitor=None if skip_binance_ping else _connection_monitor,
        skip_binance_ping=skip_binance_ping,
    )
    for check in preflight.checks:
        icon = "✅" if check.passed else "❌"
        print(f"{icon} Pre-Flight | {check.name}: {check.detail}")

    if not preflight.ok:
        print("🛑 فشل Pre-Flight — إيقاف التشغيل")
        for check in preflight.checks:
            if not check.passed:
                print(f"   ❌ {check.name}: {check.detail}")
        sys.exit(1)

    _init_persistence(settings)
    _log_project_rules_banner()
    open_n = _ssot_open_count()
    print(f"📦 مراكز بعد الاستعادة/المزامنة (SSoT): {open_n}")

    registry = get_symbol_registry()
    active_symbols = registry.load(settings.trading_pairs)
    profile = resolve_runtime_profile(settings)
    # وضع Binance فقط — لا فوركس/أسهم أبداً
    active_symbols = [
        s for s in registry.active_pairs()
        if not str(s).startswith(("FOREX/", "STOCK/"))
    ]
    print(f"📋 وضع Binance فقط: {len(active_symbols)} رمز كريبتو ({profile.label})")

    telegram_handler = TelegramCommandHandler(
        runtime=_runtime,
        executor=_executor,
        risk=_risk,
        panic=_panic,
        audit=_audit,
        price_fetcher=_fetch_prices,
    )
    _telegram_handler = telegram_handler
    if telegram_handler.enabled:
        telegram_handler.start_background_polling()

    mode = settings.execution_mode.upper()
    startup_plain = (
        f"GoldenShield AI [{settings.env}/{mode}/{profile.label}] — "
        f"أزواج: {', '.join(active_symbols)} | DB: {settings.db_path} | "
        f"مراكز:{_executor.position_manager.count()} | "
        f"max_pos:{settings.max_concurrent_positions} | build:{BUILD_TAG}"
    )
    print(f"--- 🛡️ {startup_plain} ---")
    if telegram_handler.enabled:
        # دائماً نفس لوحة التحكم + المراكز بعد الإقلاع (لا بوت «فارغ»)
        try:
            open_n = _executor.position_manager.count()
            telegram_handler.telegram.send_message(
                (
                    f"<b>✅ نفس البوت — استعادة الحالة</b>\n"
                    f"المراكز المفتوحة: <b>{open_n}</b>\n"
                    f"قاعدة البيانات ثابتة — ليست نسخة جديدة."
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("إشعار الاستعادة: %s", exc)
        try:
            telegram_handler.dashboard.send_main_menu()
        except Exception as exc:  # noqa: BLE001
            logger.warning("send_main_menu عند الإقلاع: %s", exc)
        try:
            view = telegram_handler.dashboard.render_positions(live=True)
            mid = telegram_handler.telegram.send_message(
                view.text, reply_markup=view.keyboard
            )
            if isinstance(mid, int):
                telegram_handler.dashboard.enable_live_positions(mid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("عرض المراكز عند الإقلاع: %s", exc)
        try:
            telegram_handler.dashboard.ensure_live_signals()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ensure_live_signals عند الإقلاع: %s", exc)
    else:
        startup_html = format_startup_message(
            env=settings.env,
            mode=mode,
            pairs=active_symbols,
            db_path=settings.db_path,
        )
        _alerts.send_formatted(startup_html, plain_log=f"[INFO] بدء التشغيل\n{startup_plain}")
    _maybe_send_daily_report()
    _maybe_run_daily_backup()

    while True:
        if _runtime.user_stopped or is_user_stopped():
            print("🛑 إيقاف دائم — لا إشارات ولا إعادة تشغيل حتى 00_START.bat")
            break

        _maybe_send_daily_report()
        _maybe_run_daily_backup()

        global _watchdog_cycle
        _watchdog_cycle += 1
        if _watchdog_cycle % 10 == 0:
            watchdog = ApiWatchdog().run(_connection_monitor)
            if not watchdog.ok:
                logger.warning("ApiWatchdog: %s", ", ".join(watchdog.failures))

        symbols = get_symbol_registry().active_pairs()
        loop_sec = _loop_sleep_seconds(settings)
        try:
            from operations.console_pulse import print_cycle_pulse_header

            print_cycle_pulse_header(loop_sec)
        except Exception:
            pass
        _sync_risk_session()
        _notify_kill_switch_if_needed()

        # لا تسمح ببقاء Pause بعد التشغيل إذا طُلب النشاط الدائم
        if _bot_force_active_enabled() and (_runtime.paused or _runtime.user_stopped):
            _force_bot_active(reason="cycle")

        # سياسة الإيقاف: Pause/Kill يمنعان الدخول فقط —
        # لا نوقف الدورة بالكامل (كان ذلك يوقف الإشارات = سكون)
        halt = evaluate_trading_halt(
            paused=_runtime.paused,
            kill_switch_active=bool(
                _risk.state and _risk.state.kill_switch_active
            ),
        )
        entries_blocked = bool(halt.entries_blocked)
        if entries_blocked:
            print(f"⏸️ {halt.reason} — الإشارات والبث الحي مستمران")

        if not _connection_monitor.heartbeat():
            provider = _connection_monitor.last_provider or "exchange"
            print(f"⚠️ انقطاع اتصال {provider} — تخطي هذه الدورة")
            heartbeat = check_heartbeat_guard(_connection_monitor)
            if heartbeat.should_emergency_flat:
                _emergency_flat_if_needed(heartbeat.reason, symbols)
            await asyncio.sleep(loop_sec)
            continue

        if _connection_monitor.is_disconnected():
            print(
                f"⚠️ لا اتصال منذ أكثر من {_connection_monitor.timeout_seconds} ثانية — تخطي التداول"
            )
            _emergency_flat_if_needed("انقطاع Heartbeat", symbols)
            await asyncio.sleep(loop_sec)
            continue

        market_halt = check_market_halt()
        if market_halt.halted:
            print(f"⏸️ توقف السوق: {market_halt.reason}")
            _emergency_flat_if_needed(f"توقف السوق: {market_halt.reason}", symbols)
            await asyncio.sleep(loop_sec)
            continue

        # —— Priority 0: حماية رأس المال قبل أي أوامر دخول جديدة (v1.1.2) ——
        prices = _fetch_prices(symbols)
        prices = _run_priority0_protection(symbols, prices)

        # —— ظلّ إجهاد: حسم الفرضيات المستحقة ——
        try:
            from intelligence.adaptive_weights import reinforce_from_shadow_pass
            from intelligence.shadow_stress_engine import resolve_due_shadow_hypotheses

            resolved = resolve_due_shadow_hypotheses(prices, alerts=_alerts)
            if resolved:
                reinforce_from_shadow_pass()
        except Exception as exc:  # noqa: BLE001
            logger.warning("shadow resolve: %s", exc)

        # —— عزل التنفيذ: إدارة المراكز لا تنتظر انتهاء تحليل كل الرموز ——
        try:
            inst = getattr(settings, "institutional_v13", {}) or {}
            if bool(inst.get("analysis_exec_isolation_enabled", True)):
                _run_open_position_management(prices, label="pre-analysis")
        except Exception as exc:  # noqa: BLE001
            logger.warning("pre-analysis manage_positions فشل: %s", exc)

        # —— درع انقطاع الشبكة (10s) ——
        try:
            from risk.advanced_shields import check_network_outage_shield

            outage = check_network_outage_shield(
                seconds_since_success=_connection_monitor.seconds_since_last_success(),
                is_disconnected=_connection_monitor.is_disconnected(),
            )
            if outage.block_new_entries:
                print(f"🛡️ Network Outage Shield: {outage.reason}")
                _run_open_position_management(prices, label="outage")
                await asyncio.sleep(loop_sec)
                continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("network outage shield فشل: %s", exc)

        # —— Flash Crash Circuit Breaker ——
        try:
            from risk.advanced_shields import evaluate_flash_crash

            flash = evaluate_flash_crash(prices)
            if flash.triggered:
                print(f"🚨 {flash.reason}")
                _emergency_flat_if_needed(flash.reason, symbols)
                if _risk.state is not None:
                    _risk.state.kill_switch_active = True
                    try:
                        _risk._persist()  # noqa: SLF001
                    except Exception:
                        pass
                _alerts.emergency("Flash Crash", flash.reason)
                await asyncio.sleep(loop_sec)
                continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("flash crash check فشل: %s", exc)

        # —— Weekend Flat (اختياري) ——
        try:
            from core.market_filters_extra import should_force_weekend_flat

            if should_force_weekend_flat():
                print("🗓️ Weekend Flat — إغلاق احترازي / منع دخول")
                _emergency_flat_if_needed("Weekend Flat Policy", symbols)
                await asyncio.sleep(loop_sec)
                continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("weekend flat check فشل: %s", exc)

        tri_mode = (os.getenv("TRI_COMMANDER_MODE", "true") or "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if tri_mode:
            from terminal.orchestrator import run_tri_commander_cycle

            async def _legacy(sym: str, **kw):
                return await check_symbol(sym, **kw)

            cycle_results = await run_tri_commander_cycle(
                symbols,
                executor=_executor,
                check_symbol_legacy=_legacy,
            )
        else:
            cycle_results = await asyncio.gather(*[check_symbol(s) for s in symbols])
        cycle_entries = [entry for entry in cycle_results if entry]
        # تحديث أسعار الدورة (قد تتغير بعد Priority-0)
        prices = _fetch_prices(symbols)
        if cycle_entries:
            reasons_map = {
                entry["symbol"]: entry.get("reasons", ())
                for entry in cycle_entries
            }
            telegram_handler.update_market_snapshot(
                cycle_entries,
                prices,
                reasons=reasons_map,
            )
            try:
                from datetime import datetime, timezone

                from operations.dashboard_templates import write_console_signals_board_file

                write_console_signals_board_file(
                    cycle_entries,
                    interval_seconds=float(loop_sec),
                    updated_at=datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
                    + " UTC",
                )
            except Exception as board_exc:  # noqa: BLE001
                logger.debug("signals_board write: %s", board_exc)
            _maybe_send_qualified_signals_list(telegram_handler, cycle_entries)
            _maybe_send_watchlist_digest(telegram_handler, cycle_entries)
            _maybe_send_alive_pulse(telegram_handler, cycle_entries)
            # بث حي لكل الأزواج (بما فيها WAIT) — تحديث الرسالة كل ~4 ثوانٍ
            try:
                telegram_handler.dashboard.publish_live_signals(force=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("publish_live_signals فشل: %s", exc)
        else:
            _maybe_send_alive_pulse(telegram_handler, [])
        try:
            from operations.console_pulse import print_console_signals_board

            print_console_signals_board(
                cycle_entries,
                interval_seconds=loop_sec,
            )
        except Exception as pulse_exc:  # noqa: BLE001
            logger.debug("console pulse board: %s", pulse_exc)
        _flush_opened_trades_list()
        if settings.telegram_send_cycle_signals:
            _send_cycle_signals(cycle_entries)

        _run_open_position_management(prices)

        open_count = _ssot_open_count()
        audit_count = len(_audit.decisions.records)
        if open_count:
            print(f"📊 مراكز مفتوحة: {open_count} | سجلات تدقيق: {audit_count}")

        try:
            from operations.console_pulse import print_cycle_pulse_footer

            print_cycle_pulse_footer(loop_sec, open_count=open_count)
        except Exception:
            pass
        try:
            from operations.mobile_runtime_mirror import push_runtime_mirror

            push_runtime_mirror(getattr(_risk, "state", None))
        except Exception as mirror_exc:  # noqa: BLE001
            logger.debug("mobile_runtime_mirror: %s", mirror_exc)
        await asyncio.sleep(loop_sec)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        _runtime.stop_permanently(reason="keyboard_interrupt")
        print("\n--- 🛑 تم إيقاف البوت بقرارك — لن يُعاد التشغيل تلقائياً ---")
    except Exception:
        if not is_user_stopped():
            logger.exception("توقف غير متوقع — المشرف سيعيد التشغيل")
            raise
        print("--- 🛑 البوت متوقف ---")
