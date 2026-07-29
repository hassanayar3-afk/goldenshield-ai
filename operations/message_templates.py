"""قوالب رسائل Telegram — تنسيق HTML احترافي موحّد."""

from __future__ import annotations

import html
import re
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audit.audit_trail import AuditTrail
    from execution.trade_executor import TradeExecutor
    from risk.risk_orchestrator import RiskOrchestrator

DIVIDER = "━━━━━━━━━━━━━━━"
_BRAND = "🛡️ <b>GoldenShield AI</b>"

_LEVEL_META: dict[str, tuple[str, str]] = {
    "info": ("ℹ️", "معلومة"),
    "warning": ("⚠️", "تنبيه"),
    "emergency": ("🚨", "طوارئ"),
}


def escape(text: object) -> str:
    return html.escape(str(text), quote=False)


def strip_html(text: str) -> str:
    plain = re.sub(r"<[^>]+>", "", text)
    return plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _header(subtitle: str | None = None) -> str:
    lines = [_BRAND, DIVIDER]
    if subtitle:
        lines.append(f"<i>{escape(subtitle)}</i>")
    return "\n".join(lines)


def _money(value: float, currency: str = "USDT") -> str:
    return f"<code>{value:,.2f}</code> {escape(currency)}"


def _score(value: int | float, maximum: int = 10) -> str:
    return f"<code>{value}/{maximum}</code>"


def format_alert_message(level: str, title: str, detail: str = "") -> str:
    icon, _ = _LEVEL_META.get(level, ("ℹ️", "معلومة"))
    lines = [
        _header(),
        f"{icon} <b>{escape(title)}</b>",
    ]
    if detail:
        lines.append("")
        lines.append(escape(detail))
    return "\n".join(lines)


def format_infrastructure_alert(
    *,
    level: str,
    title: str,
    checks: list,
    summary: str = "",
    checked_at: str = "",
    footer: str = "",
) -> str:
    """تنبيه تشخيصي: أين الخلل + التشخيص + ماذا تفعل."""
    icon, _ = _LEVEL_META.get(level, ("ℹ️", "معلومة"))
    lines = [
        _header("مراقبة آلية 24/7"),
        f"{icon} <b>{escape(title)}</b>",
    ]
    if checked_at:
        lines.append(f"<i>وقت الفحص (UTC): {escape(checked_at)}</i>")
    if summary:
        lines.extend(["", f"📌 <b>الملخص:</b> {escape(summary)}"])

    failures = [c for c in checks if not getattr(c, "ok", False)]
    successes = [c for c in checks if getattr(c, "ok", False)]

    if failures:
        lines.extend(["", "━━━━━━━━━━━━━━━", "🚨 <b>التشخيص التفصيلي</b>"])
        for i, check in enumerate(failures, 1):
            name = escape(getattr(check, "name", "?"))
            location = escape(getattr(check, "location", "") or "غير محدد")
            detail = escape(getattr(check, "detail", ""))
            diagnosis = escape(getattr(check, "diagnosis", "") or detail)
            action = escape(getattr(check, "action", "") or "راجع السجلات.")
            lines.append("")
            lines.append(f"<b>{i}) الخلل:</b> {name}")
            lines.append(f"<b>المكان:</b> {location}")
            lines.append(f"<b>الملاحظة:</b> {detail}")
            lines.append(f"<b>التشخيص:</b> {diagnosis}")
            lines.append(f"<b>ماذا تفعل:</b>")
            for step in action.split("\n"):
                step = step.strip()
                if step:
                    lines.append(f"• <code>{step}</code>" if not step[0].isdigit() else f"• {step}")

    if successes:
        lines.extend(["", "━━━━━━━━━━━━━━━", "✅ <b>سليم حالياً</b>"])
        for check in successes:
            lines.append(
                f"• {escape(getattr(check, 'name', '?'))}"
                f" — <i>{escape(getattr(check, 'detail', ''))}</i>"
            )

    if footer:
        lines.extend(["", f"<i>{escape(footer)}</i>"])
    return "\n".join(lines)


def format_startup_message(*, env: str, mode: str, pairs: list[str], db_path: str) -> str:
    pairs_text = ", ".join(pairs)
    return "\n".join(
        [
            _header("بدء التشغيل"),
            "✅ <b>البوت يعمل الآن</b>",
            "",
            f"البيئة: <code>{escape(env.upper())}</code>",
            f"الوضع: <code>{escape(mode.upper())}</code>",
            f"الأزواج: <b>{escape(pairs_text)}</b>",
            f"قاعدة البيانات: <code>{escape(db_path)}</code>",
        ]
    )


def _signal_row_icon(signal: str) -> str:
    if signal == "BUY SIGNAL":
        return "🟢"
    if signal == "SELL SIGNAL":
        return "🔴"
    if signal == "REJECTED":
        return "⛔"
    if signal in {"HALTED", "HALT"}:
        return "⏸️"
    return "⏳"


def format_signal_message(
    *,
    symbol: str,
    price: float,
    score: int,
    signal: str,
    extra: str = "",
    kind: str,
) -> str:
    from core.constants import score_to_percent
    from operations.dashboard_templates import simple_signal_label, simple_strength_stars

    kind_meta = {
        "buy": ("🟢", "فرصة شراء جاهزة"),
        "sell": ("🔴", "فرصة بيع جاهزة"),
        "rejected": ("⛔", "فرصة مرفوضة"),
        "halted": ("⏸️", "السوق متوقف"),
    }
    icon, title = kind_meta[kind]
    from data.symbol_routing import display_symbol, format_price

    coin = escape(display_symbol(symbol))
    lines = [
        _header(title),
        f"{icon} <b>{coin}</b>",
        "",
        f"📍 السعر: <code>{escape(format_price(symbol, price))}</code>",
        f"💪 قوة الفرصة: {simple_strength_stars(score)} ({score_to_percent(score)}/100)",
        f"📡 الحالة: <b>{escape(simple_signal_label(signal))}</b>",
    ]
    if kind == "buy":
        lines.append("")
        lines.append("✅ <b>اضغط «دخول الصفقة» إذا توافق.</b>")
    if extra:
        lines.extend(["", f"📌 {escape(extra)}"])
    return "\n".join(lines)


def format_cycle_signals_message(entries: list[dict]) -> str:
    from operations.dashboard_templates import simple_signal_label, simple_strength_label

    lines = [_header("تحديث السوق"), ""]
    from data.symbol_routing import display_symbol

    for entry in entries:
        signal = str(entry["signal"])
        coin = escape(display_symbol(entry["symbol"]))
        score = int(entry["score"])
        lines.append(
            f"{_signal_row_icon(signal)} <b>{coin}</b> — "
            f"{escape(simple_signal_label(signal))} · {escape(simple_strength_label(score))}"
        )
    return "\n".join(lines)


def format_trade_open_message(symbol: str, detail: str) -> str:
    return "\n".join(
        [
            _header("صفقة جديدة"),
            f"📈 <b>{escape(symbol)}</b>",
            "",
            escape(detail),
        ]
    )


def format_opened_trades_digest(opened: list[dict]) -> str:
    """قائمة عمودية مريحة بأيقونات — مرتبة من الأضعف للأقوى."""
    from core.constants import score_to_percent
    from data.symbol_routing import display_symbol, format_price

    ordered = sorted(
        opened,
        key=lambda e: (int(e.get("score") or 0), str(e.get("symbol") or "")),
    )
    lines = [
        _header("صفقات فُتحت"),
        "",
        f"<b>العدد:</b> {len(ordered)}  ·  من الأضعف → الأقوى",
        "",
    ]
    if not ordered:
        lines.append("لا صفقات جديدة.")
        return "\n".join(lines)

    for i, item in enumerate(ordered, start=1):
        symbol = str(item.get("symbol") or "")
        coin = escape(display_symbol(symbol))
        side_raw = str(item.get("side") or "")
        if side_raw in {"بيع", "SELL", "sell"}:
            side_icon, side_ar = "🔴", "بيع"
        elif side_raw in {"شراء", "BUY", "buy"}:
            side_icon, side_ar = "🟢", "شراء"
        else:
            side_icon, side_ar = "📈", side_raw or "—"

        score = item.get("score")
        pct = score_to_percent(int(score)) if score is not None else 0
        mode = str(item.get("mode") or "LIVE")
        mode_icon = "🔴" if mode == "LIVE" else "🟡"
        mode_ar = "مباشر" if mode == "LIVE" else "تجريبي"

        if item.get("entry") is not None:
            entry_txt = format_price(symbol, float(item["entry"]))
            sl_txt = format_price(symbol, float(item.get("sl") or 0))
            tp_txt = format_price(symbol, float(item.get("tp") or 0))
        else:
            entry_txt = sl_txt = tp_txt = "—"

        amount = item.get("amount")
        amount_txt = f"{float(amount):g}" if amount is not None else "—"

        lines.append(
            f"<b>{i}.</b> 📊 <b>{coin}</b>  ·  {side_icon} {side_ar}"
            + (f"  ·  💪 <code>{pct}/100</code>" if pct else "")
        )
        lines.append(f"   {mode_icon} الوضع: <b>{escape(mode_ar)}</b> <code>[{escape(mode)}]</code>")
        lines.append(f"   📦 الكمية: <code>{escape(amount_txt)}</code>")
        lines.append(f"   🎯 الدخول: <code>{escape(entry_txt)}</code>")
        lines.append(f"   🛑 SL: <code>{escape(sl_txt)}</code>")
        lines.append(f"   💎 TP: <code>{escape(tp_txt)}</code>")
        lines.append("")

    lines.append("<i>راجع التفاصيل من 📂 مراكزي</i>")
    return "\n".join(lines).rstrip()


def format_trade_close_message(symbol: str, pnl: float, reason: str) -> str:
    sign = "+" if pnl >= 0 else ""
    pnl_icon = "🟢" if pnl >= 0 else "🔴"
    return "\n".join(
        [
            _header("إغلاق صفقة"),
            f"{pnl_icon} <b>{escape(symbol)}</b>",
            "",
            f"النتيجة: <b>{sign}{pnl:,.2f} USDT</b>",
            f"السبب: {escape(reason)}",
        ]
    )


def format_emergency_message(title: str, detail: str) -> str:
    return "\n".join(
        [
            _header("طوارئ"),
            f"🚨 <b>{escape(title)}</b>",
            "",
            escape(detail),
        ]
    )


def format_daily_report_plain(
    *,
    risk: RiskOrchestrator,
    executor: TradeExecutor,
    audit: AuditTrail | None = None,
    report_date: date | None = None,
) -> str:
    today = report_date or date.today()
    state = risk.state
    open_positions = executor.position_manager.count()
    audit_count = len(audit.decisions.records) if audit else 0

    if state is None:
        return f"📋 تقرير {today.isoformat()}\nلا توجد بيانات جلسة مخاطر بعد."

    pnl_sign = "+" if state.daily_pnl_pct >= 0 else ""
    kill = "مفعّل 🛑" if state.kill_switch_active else "غير مفعّل ✅"
    net = state.daily_net_pnl
    net_sign = "+" if net >= 0 else ""

    lines = [
        f"📋 تقرير GoldenShield — {today.isoformat()}",
        f"الرصيد: {state.current_balance:.2f} USDT",
        f"ربح اليوم: +{state.daily_profit:.2f} USDT",
        f"خسارة اليوم: -{state.daily_loss:.2f} USDT",
        f"صافي اليوم: {net_sign}{net:.2f} USDT ({pnl_sign}{state.daily_pnl_pct:.2f}%)",
        f"صفقات اليوم: {state.daily_trades}",
        f"خسائر متتالية: {state.consecutive_losses}",
        f"أرباح متتالية: {getattr(state, 'consecutive_wins', 0)}",
        f"Kill Switch: {kill}",
        f"مراكز مفتوحة: {open_positions}",
        f"سجلات تدقيق: {audit_count}",
    ]

    # أداء موسّع: Win Rate + أفضل زوج + متوسط انزلاق إن توفر
    try:
        wins = 0
        losses = 0
        best_pair = "-"
        best_pnl = float("-inf")
        slip_samples: list[float] = []
        if audit is not None:
            for rec in getattr(audit.decisions, "records", []) or []:
                pnl = getattr(rec, "pnl", None)
                sym = getattr(rec, "symbol", None) or getattr(rec, "pair", None)
                action = str(getattr(rec, "action", "") or getattr(rec, "decision", "")).lower()
                if pnl is None:
                    continue
                try:
                    pnl_f = float(pnl)
                except (TypeError, ValueError):
                    continue
                if "exit" in action or "close" in action or pnl_f != 0:
                    if pnl_f >= 0:
                        wins += 1
                    else:
                        losses += 1
                    if sym and pnl_f > best_pnl:
                        best_pnl = pnl_f
                        best_pair = str(sym)
                slip = getattr(rec, "slippage_pct", None) or getattr(rec, "slippage", None)
                if slip is not None:
                    try:
                        slip_samples.append(float(slip))
                    except (TypeError, ValueError):
                        pass
        closed = wins + losses
        winrate = (wins / closed * 100.0) if closed else 0.0
        avg_slip = (sum(slip_samples) / len(slip_samples)) if slip_samples else 0.0
        lines.append(f"Win Rate: {winrate:.1f}% ({wins}W/{losses}L)")
        lines.append(f"أفضل زوج: {best_pair}" + (f" ({best_pnl:+.2f})" if best_pair != "-" else ""))
        lines.append(f"متوسط الانزلاق: {avg_slip:.4f}%")
    except Exception:
        pass

    return "\n".join(lines)


def format_daily_report_telegram(
    *,
    risk: RiskOrchestrator,
    executor: TradeExecutor,
    audit: AuditTrail | None = None,
    report_date: date | None = None,
) -> str:
    today = report_date or date.today()
    state = risk.state
    open_positions = executor.position_manager.count()

    if state is None:
        return "\n".join(
            [
                _header("تقرير اليوم"),
                f"📅 <b>{today.isoformat()}</b>",
                "",
                "لا توجد بيانات جلسة مخاطر بعد.",
            ]
        )

    pnl_sign = "+" if state.daily_pnl_pct >= 0 else ""
    pnl_icon = "📈" if state.daily_pnl_pct >= 0 else "📉"
    net = state.daily_net_pnl
    net_sign = "+" if net >= 0 else ""

    return "\n".join(
        [
            _header("تقرير اليوم"),
            f"📅 <b>{today.isoformat()}</b>",
            "",
            f"💰 رصيدك: {_money(state.current_balance)}",
            f"🟢 ربح اليوم: <b>+{state.daily_profit:,.2f} $</b>",
            f"🔴 خسارة اليوم: <b>-{state.daily_loss:,.2f} $</b>",
            f"{pnl_icon} صافي اليوم: <b>{net_sign}{net:,.2f} $</b> "
            f"({pnl_sign}{state.daily_pnl_pct:.2f}%)",
            f"🔄 صفقات اليوم: <b>{state.daily_trades}</b>",
            f"📂 صفقات مفتوحة: <b>{open_positions}</b>",
        ]
    )


def format_status_message(
    *,
    bot_username: str | None,
    paused: bool,
    balance: float,
    daily_pnl: str,
    open_count: int,
    kill_switch: str,
) -> str:
    status = "موقوف ⏸️" if paused else "نشط ✅"
    username = f"@{bot_username}" if bot_username else "غير مُعرَّف"
    return "\n".join(
        [
            _header("الحالة الحالية"),
            f"🤖 البوت: <b>{escape(username)}</b>",
            f"⚙️ الحالة: <b>{status}</b>",
            "",
            f"💰 الرصيد: {_money(balance)}",
            f"📊 PnL اليوم: <b>{escape(daily_pnl)}</b>",
            f"📂 المراكز: <b>{open_count}</b>",
            f"🛑 Kill Switch: <b>{escape(kill_switch)}</b>",
        ]
    )


def format_command_reply(command: str, message: str) -> str:
    labels = {
        "/pause": "إيقاف مؤقت",
        "/resume": "استئناف",
        "/panic": "زر الطوارئ",
    }
    label = labels.get(command, "أمر")
    return "\n".join(
        [
            _header(label),
            escape(message),
        ]
    )


def format_help_message() -> str:
    return "\n".join(
        [
            _header("دليل سريع"),
            "",
            "🏠 <b>/start</b> — القائمة الرئيسية",
            "📡 <b>/market</b> — ماذا يحدث في السوق؟",
            "📂 <b>/positions</b> — صفقاتك المفتوحة",
            "⏸️ <b>/pause</b>  |  ▶️ <b>/resume</b>",
            "🚨 <b>/panic</b> — إغلاق كل الصفقات + إيقاف كامل",
            "⛔ <b>/stop</b> — إيقاف كامل بدون إغلاق صفقات",
            "📉 <b>/losses</b> — تقارير الصفقات الخاسرة",
            "🔎 <b>/loss_detail BTC/USDT</b> — تفاصيل خسارة رمز",
            "",
            "<i>بعد /panic أو /stop: لا إشارات ولا إعادة تشغيل — شغّل 00_START.bat للعودة.</i>",
            "",
            "<b>إدارة الرموز (Binance):</b>",
            "➕ <b>/add BTC/USDT</b> — إضافة عملة",
            "📋 <b>/symbols</b> — قائمة الرموز",
            "🗑️ <b>/remove SYMBOL</b> — إيقاف مراقبة رمز",
            "",
            "<i>MetaTrader/فوركس/أسهم معطّلة — المشروع على Binance فقط.</i>",
            "",
            "<b>متى يظهر زر الدخول؟</b>",
            "فقط عند فرصة قوية (75/100) + إشارة شراء.",
            "إذا لم يظهر — السوق يقول «انتظر» وهذا طبيعي.",
        ]
    )
