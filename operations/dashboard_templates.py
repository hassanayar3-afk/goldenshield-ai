"""قوالب لوحة تحكم Telegram — بطاقات تداول احترافية."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from config.settings import get_settings
from core.constants import (
    SIGNAL_MIN_PERCENT,
    meets_signal_minimum,
    meets_telegram_notify_minimum,
    score_to_percent,
)
from operations.message_templates import DIVIDER, _BRAND, _money, escape

if TYPE_CHECKING:
    from execution.models.trade import Position
    from risk.risk_orchestrator import RiskApproval, RiskOrchestrator
    from execution.trade_executor import TradeExecutor


@dataclass(frozen=True)
class RiskGrade:
    score: int
    icon: str
    label: str
    bar: str
    color_hint: str


def simple_signal_label(signal: str) -> str:
    mapping = {
        "BUY SIGNAL": "فرصة شراء",
        "SELL SIGNAL": "فرصة بيع",
        "WAIT": "انتظر",
        "REJECTED": "مرفوضة",
        "HALTED": "السوق متوقف",
        "HALT": "السوق متوقف",
    }
    return mapping.get(signal, signal)


def simple_strength_stars(score: int, *, maximum: int = 10) -> str:
    """شريط قوة — دوائر بدل النجوم."""
    percent = score_to_percent(score)
    filled = max(0, min(maximum, percent // 10))
    return "●" * filled + "○" * (maximum - filled)


def simple_strength_label(score: int) -> str:
    percent = score_to_percent(score)
    if percent >= SIGNAL_MIN_PERCENT:
        return "قوية جداً — جاهزة للدخول"
    if percent >= 70:
        return "جيدة — راقبها"
    if percent >= 50:
        return "متوسطة — لا تدخل الآن"
    return "ضعيفة — تجنب الدخول"


def risk_grade_from_score(score: int, *, signal: str = "WAIT") -> RiskGrade:
    percent = score_to_percent(score)
    if signal in {"HALTED", "HALT"}:
        return RiskGrade(score, "⛔", "السوق متوقف", "░░░░░", "halted")
    if signal == "REJECTED":
        return RiskGrade(score, "🚫", "مرفوضة", "█░░░░", "rejected")
    if percent >= SIGNAL_MIN_PERCENT:
        return RiskGrade(score, "🟢", "جاهزة للدخول", "█████", "low")
    if percent >= 70:
        return RiskGrade(score, "🟡", "راقبها", "████░", "medium")
    if percent >= 50:
        return RiskGrade(score, "🟠", "انتظر", "███░░", "moderate")
    return RiskGrade(score, "🔴", "ضعيفة", "██░░░", "high")


def format_entry_block_reason(
    *,
    signal: str,
    score: int,
    premium: bool,
    paused: bool,
    has_position: bool,
    approval_approved: bool,
    approval_reason: str = "",
) -> str:
    """رسالة بسيطة تشرح لماذا لا يظهر زر الدخول."""
    if paused:
        return "التداول موقوف — اضغط ▶️ تشغيل من القائمة الرئيسية."
    if has_position:
        return "لديك صفقة مفتوحة على هذه العملة — راجعها من 📂 مراكزي."
    if signal not in {"BUY SIGNAL", "SELL SIGNAL"}:
        if meets_signal_minimum(score):
            return (
                f"السوق على «{simple_signal_label(signal)}» بقوة {score_to_percent(score)}/100 — "
                "الزر يفتح دخولاً إجبارياً حسب الاتجاه إن وُجد."
            )
        return f"السوق يقول «{simple_signal_label(signal)}» — ليس وقت دخول الآن."
    if not meets_signal_minimum(score):
        return (
            f"القوة {score_to_percent(score)}/100 — نحتاج {SIGNAL_MIN_PERCENT} على الأقل "
            f"ليظهر زر ✅ دخول الصفقة."
        )
    if not approval_approved:
        reason = approval_reason.strip() or "نظام الحماية يمنع الدخول حالياً."
        return f"🛡️ {reason}"
    if not premium:
        return "الإشارة لم تكتمل بعد — انتظر التحديث القادم."
    return ""


def _header(subtitle: str) -> str:
    return f"{_BRAND}\n{DIVIDER}\n<i>{escape(subtitle)}</i>"


def _pct_change(entry: float, target: float) -> str:
    if entry <= 0:
        return "0.00%"
    pct = ((target - entry) / entry) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def format_main_dashboard(
    *,
    env: str,
    mode: str,
    balance: float,
    daily_pnl: str,
    open_count: int,
    paused: bool,
    kill_switch: str,
    pairs_count: int,
    manual_mode: bool = True,
) -> str:
    status = "موقوف ⏸️" if paused else "يعمل ✅"
    mode_note = "تجريبي" if mode.upper() == "PAPER" else "حقيقي"
    auto_pct = get_settings().auto_entry_min_percent
    if auto_pct >= 100:
        entry_note = "ذهبي ⚡"
        mode_hint = (
            "<i>⚡ دخول تلقائي للفرص الذهبية فقط 100/100 — "
            f"🖐 يدوي من تيليجرام عند {SIGNAL_MIN_PERCENT}–99/100.</i>"
        )
    elif auto_pct <= SIGNAL_MIN_PERCENT:
        entry_note = "تلقائي ⚡"
        mode_hint = f"<i>⚡ دخول تلقائي لكل فرصة ≥ {SIGNAL_MIN_PERCENT}/100 (وضع الاختبار).</i>"
    else:
        entry_note = "مختلط ⚡🖐"
        mode_hint = (
            f"<i>⚡ تلقائي من {auto_pct}/100 فما فوق — "
            f"🖐 يدوي من تيليجرام عند {SIGNAL_MIN_PERCENT}–{max(SIGNAL_MIN_PERCENT, auto_pct - 1)}/100.</i>"
        )
    return "\n".join(
        [
            _header("الرئيسية"),
            "",
            f"🤖 البوت <b>{status}</b>  |  وضع <b>{mode_note}</b>  |  دخول <b>{entry_note}</b>",
            "",
            f"💰 رصيدك: <b>{_money(balance)}</b>",
            f"📈 نتيجة اليوم: <b>{escape(daily_pnl)}</b>",
            f"📂 صفقات مفتوحة: <b>{open_count}</b>",
            "",
            f"📡 يراقب <b>{pairs_count}</b> عملات",
            "",
            mode_hint,
            "<i>اضغط 📡 الإشارات لمتابعة السوق.</i>",
        ]
    )


def _market_row(entry: dict) -> str:
    """سطر عمودي مريح مع أيقونات — لنفس ترتيب القائمة."""
    from data.symbol_routing import display_symbol, format_price

    score = int(entry["score"])
    signal = str(entry["signal"])
    grade = risk_grade_from_score(score, signal=signal)
    coin = escape(display_symbol(entry["symbol"]))
    percent = score_to_percent(score)
    price = float(entry.get("price") or 0)
    price_txt = format_price(entry["symbol"], price) if price > 0 else "—"

    if signal == "BUY SIGNAL":
        side_icon, side_ar = "🟢", "شراء"
    elif signal == "SELL SIGNAL":
        side_icon, side_ar = "🔴", "بيع"
    else:
        side_icon, side_ar = "⚪", simple_signal_label(signal)

    action = str(entry.get("entry_action") or "")
    if "تلقائي" in action:
        entry_line = "⚡ دخول: <b>تلقائي</b>"
    elif "يدوي" in action:
        entry_line = "🖐 دخول: <b>يدوي</b>"
    else:
        entry_line = ""

    lines = [
        f"{grade.icon} <b>{coin}</b>  ·  {side_icon} {side_ar}  ·  💪 <code>{percent}/100</code>",
        f"   💰 السعر: <code>{escape(price_txt)}</code>",
    ]
    if entry_line:
        lines.append(f"   {entry_line}")
    return "\n".join(lines)


def format_qualified_signals_digest(entries: list[dict]) -> str:
    """قائمة عمودية بأيقونات — مرتبة من الأضعف للأقوى (≥85 شراء/بيع للإرسال)."""
    ordered = sorted(
        entries,
        key=lambda e: (int(e.get("score", 0)), str(e.get("symbol") or "")),
    )
    lines = [
        _header("صفقات جاهزة للدخول"),
        "",
        f"<b>الفرص:</b> {len(ordered)}  ·  من الأضعف → الأقوى",
        "",
    ]
    if not ordered:
        lines.append("لا توجد صفقة جاهزة للدخول حالياً.")
        return "\n".join(lines)

    for i, entry in enumerate(ordered, start=1):
        lines.append(f"<b>{i}.</b> {_market_row(entry)}")
        lines.append("")

    lines.append("<i>اضغط زر الزوج لفتح التفاصيل</i>")
    return "\n".join(lines).rstrip()


def format_market_overview(all_entries: list[dict]) -> str:
    """قائمة واحدة مجمّعة — من الأضعف للأقوى."""
    ordered = sorted(all_entries, key=lambda e: int(e.get("score", 0)))

    lines = [
        _header("الإشارات"),
        "",
        "<i>كل الأزواج في قائمة واحدة (من الأضعف → الأقوى)</i>",
        "<i>اضغط زر الزوج لفتح تفاصيل الصفقة</i>",
        "",
        f"<b>المراقبة:</b> {len(ordered)} زوج",
        "",
    ]

    if not ordered:
        lines.append("لا توجد بيانات بعد — انتظر دورة التحليل.")
        return "\n".join(lines)

    for entry in ordered:
        lines.append(_market_row(entry))
        lines.append("")

    lines.append("<i>◀️ رجوع من زر الرئيسية أسفل الأزرار</i>")
    return "\n".join(lines).rstrip()


def format_watchlist_digest(all_entries: list[dict]) -> str:
    """ملخص سريع يُرسل عند التشغيل — كل العملات المراقبة."""
    return format_market_overview(all_entries)


def format_live_signals_board(
    all_entries: list[dict],
    *,
    interval_seconds: int = 15,
    updated_at: str = "",
) -> str:
    """لوحة إشارات حية مضغوطة — كل الأزواج بما فيها WAIT."""
    from data.symbol_routing import display_symbol

    ordered = sorted(
        all_entries,
        key=lambda e: (-int(e.get("score", 0) or 0), str(e.get("symbol") or "")),
    )
    ready = [
        e
        for e in ordered
        if str(e.get("signal")) in {"BUY SIGNAL", "SELL SIGNAL"}
        and meets_telegram_notify_minimum(int(e.get("score", 0) or 0))
        and e.get("passed") is not False
    ]
    stamp = escape(updated_at) if updated_at else "—"
    lines = [
        _header("بث حي — الإشارات"),
        "",
        f"<i>يتحدّث تلقائياً كل ~{int(interval_seconds)} ثانية</i>",
        f"<b>آخر تحديث:</b> <code>{stamp}</code>",
        f"<b>المراقبة:</b> {len(ordered)}  ·  <b>جاهزة:</b> {len(ready)}",
        "",
    ]
    if not ordered:
        lines.append("لا توجد بيانات بعد — انتظر دورة التحليل.")
        return "\n".join(lines)

    for entry in ordered:
        score = int(entry.get("score", 0) or 0)
        percent = score_to_percent(score)
        signal = str(entry.get("signal") or "WAIT")
        coin = escape(display_symbol(str(entry.get("symbol") or "?")))
        if signal == "BUY SIGNAL":
            icon, label = "🟢", "شراء"
        elif signal == "SELL SIGNAL":
            icon, label = "🔴", "بيع"
        elif signal == "REJECTED":
            icon, label = "🚫", "مرفوض"
        else:
            icon, label = "⚪", "انتظر"
        stars = simple_strength_stars(score, maximum=10)
        lines.append(
            f"{icon} <b>{coin}</b>  {escape(label)}  "
            f"<code>{percent}/100</code>  {stars}"
        )

    lines.extend(
        [
            "",
            "<i>التلقائي من 90/100 فما فوق (درجة 9–10) — أقل من ذلك يدوي أو انتظار</i>",
            "<i>اضغط «📡 الإشارات» من القائمة للتفاصيل</i>",
        ]
    )
    return "\n".join(lines)


def _line(icon: str, label: str, value: str, extra: str = "") -> str:
    """سطر واحد منظم ومحاذي: أيقونة + تسمية ثابتة العرض + قيمة."""
    label_pad = f"{label:<8}"
    base = f"│  {icon}  <code>{escape(label_pad)}</code>  <code>{value}</code>"
    if extra:
        return f"{base}  <code>{extra}</code>"
    return base


def format_trade_setup_card(
    *,
    symbol: str,
    price: float,
    score: int,
    signal: str,
    approval: RiskApproval | None = None,
    reasons: tuple[str, ...] | list[str] = (),
    prefs_label: str = "",
    risk_pct: float | None = None,
    can_enter: bool = False,
    entry_block_reason: str = "",
    balance: float | None = None,
) -> str:
    from risk.lot_calculator import LotCalculator

    settings = get_settings()
    grade = risk_grade_from_score(score, signal=signal)
    from data.symbol_routing import display_symbol, format_price

    coin = escape(display_symbol(symbol))
    percent = score_to_percent(score)
    used_risk = risk_pct if risk_pct is not None else settings.risk_per_trade_pct
    account = balance if balance is not None and balance > 0 else 10_000.0
    side = "sell" if signal == "SELL SIGNAL" else "buy"
    side_ar = "بيع" if side == "sell" else "شراء"

    if approval is not None and approval.amount > 0 and approval.stop_loss > 0:
        entry = price
        sl = approval.stop_loss
        tp = approval.take_profit
        amount = approval.amount
    else:
        amount, sl, tp = LotCalculator(account).calculate(
            price, risk_pct=used_risk, side=side
        )
        entry = price
        if amount <= 0:
            if side == "sell":
                sl = price * (1 + settings.default_sl_pct)
                tp = price * (1 - settings.default_sl_pct * settings.default_rr_ratio)
            else:
                sl = price * (1 - settings.default_sl_pct)
                tp = price * (1 + settings.default_sl_pct * settings.default_rr_ratio)

    points_risk = abs(entry - sl)
    points_profit = abs(tp - entry)
    risk_usdt = points_risk * amount if amount > 0 else account * (used_risk / 100.0)
    profit_usdt = (
        points_profit * amount
        if amount > 0
        else risk_usdt
        * (points_profit / points_risk if points_risk > 0 else settings.default_rr_ratio)
    )
    rr = (points_profit / points_risk) if points_risk > 0 else settings.default_rr_ratio
    status = "جاهزة للدخول ✅" if can_enter else simple_signal_label(signal)

    lines = [
        _BRAND,
        DIVIDER,
        f"<b>{coin}</b>  ·  {side_ar}",
        "",
        f"{grade.icon}  <b>قوة الصفقة</b>  ·  <code>{percent}/100</code>",
        f"{simple_strength_stars(score)}",
        f"<i>{escape(simple_strength_label(score))}</i>",
        "",
        "┌─ <b>تفاصيل الصفقة</b>",
        _line("🎯", "Entry", format_price(symbol, entry)),
        _line("🛑", "SL", format_price(symbol, sl), _pct_change(entry, sl)),
        _line("💎", "TP", format_price(symbol, tp), _pct_change(entry, tp)),
        "└────────────────",
        "",
        "┌─ <b>المخاطر والأرباح</b>",
        _line("⚠️", "الخطورة", f"{used_risk:.1f}%", f"{risk_usdt:,.2f} $"),
        _line("📉", "الخسارة", f"{points_risk:,.5f}", f"{risk_usdt:,.2f} $"),
        _line("📈", "الربح", f"+{points_profit:,.5f}", f"+{profit_usdt:,.2f} $"),
        _line("⚖️", "نسبة الهدف", f"+{profit_usdt:,.2f} $", f"1:{rr:.1f}"),
        "└────────────────",
        "",
        f"📌  <b>الحالة</b>  ·  {escape(status)}",
    ]

    auto_pct = settings.auto_entry_min_percent
    if can_enter and percent >= auto_pct and auto_pct >= 100:
        lines.append(
            "<b>⚡ فرصة ذهبية — قد تُفتح تلقائياً</b> (100/100) — أو اضغط الزر إن لم تُفتح بعد"
        )
    elif can_enter and percent >= auto_pct:
        lines.append(
            f"<b>⚡ قد تُفتح تلقائياً</b> (قوة ≥ {auto_pct}/100) — أو اضغط الزر إن لم تُفتح بعد"
        )
    elif can_enter:
        lines.append(
            f"<b>➜ يدوي:</b> اضغط «دخول الصفقة الآن» "
            f"(التلقائي من {auto_pct}/100 فما فوق)"
        )
    elif entry_block_reason:
        lines.append(f"<i>{escape(entry_block_reason)}</i>")

    if reasons:
        lines.append("")
        lines.append("📋 <b>أسباب الإشارة</b>")
        for reason in reasons[:4]:
            lines.append(f"• {escape(reason)}")

    return "\n".join(lines)


def format_position_card(
    position: Position,
    *,
    current_price: float,
    balance: float,
) -> str:
    from core.constants import score_to_percent
    from data.symbol_routing import display_symbol, format_price

    if position.side.value == "buy":
        unrealized = (current_price - position.entry_price) * position.amount
        pnl_pct = (
            ((current_price - position.entry_price) / position.entry_price) * 100
            if position.entry_price > 0
            else 0.0
        )
        side_ar = "شراء"
    else:
        unrealized = (position.entry_price - current_price) * position.amount
        pnl_pct = (
            ((position.entry_price - current_price) / position.entry_price) * 100
            if position.entry_price > 0
            else 0.0
        )
        side_ar = "بيع"

    sign = "+" if unrealized >= 0 else ""
    pnl_sign = "+" if pnl_pct >= 0 else ""
    pnl_icon = "🟢" if unrealized >= 0 else "🔴"

    coin = escape(display_symbol(position.symbol))
    mode = "تجريبي" if position.is_paper else "حقيقي"
    risk_usdt = position.risk_per_unit * position.amount
    risk_pct_val = (risk_usdt / balance * 100) if balance > 0 else 0.0
    points_to_tp = abs(position.take_profit - position.entry_price)
    profit_at_tp = points_to_tp * position.amount
    points_risk = position.risk_per_unit
    rr = points_to_tp / points_risk if points_risk > 0 else 0.0
    be = "مفعّل" if position.breakeven_applied else "انتظار"
    partial = "تم" if position.partial_exit_done else "لا"
    opened = position.opened_at.strftime("%Y-%m-%d %H:%M") if position.opened_at else "—"
    strength = score_to_percent(position.signal_score) if position.signal_score > 0 else 0
    strength_txt = f"{strength}/100" if strength > 0 else "—"
    sl_pct = _pct_change(position.entry_price, position.stop_loss)
    tp_pct = _pct_change(position.entry_price, position.take_profit)

    return "\n".join(
        [
            _BRAND,
            DIVIDER,
            f"<b>{coin}</b>  ·  {side_ar}  ·  {escape(mode)}",
            "",
            f"⚡  <b>قوة الدخول</b>  ·  <code>{escape(strength_txt)}</code>",
            f"{pnl_icon}  <b>النتيجة الآن</b>  ·  "
            f"<code>{sign}{unrealized:,.2f} $</code>  ·  "
            f"<code>{pnl_sign}{pnl_pct:.2f}%</code>",
            "",
            "┌─ <b>مستويات الصفقة</b>",
            _line("🎯", "Entry", format_price(position.symbol, position.entry_price)),
            _line(
                "📍",
                "Price",
                format_price(position.symbol, current_price),
                _pct_change(position.entry_price, current_price),
            ),
            _line(
                "🛑",
                "SL",
                format_price(position.symbol, position.stop_loss),
                sl_pct,
            ),
            _line(
                "💎",
                "TP",
                format_price(position.symbol, position.take_profit),
                tp_pct,
            ),
            "└────────────────",
            "",
            "┌─ <b>المخاطر والأرباح</b>",
            _line("⚠️", "الخطورة", f"{risk_pct_val:.2f}%", f"{risk_usdt:,.2f} $"),
            _line("📉", "الخسارة", f"{points_risk:,.2f} نقطة", f"{risk_usdt:,.2f} $"),
            _line("📈", "الربح", f"+{points_to_tp:,.2f} نقطة", f"+{profit_at_tp:,.2f} $"),
            _line("⚖️", "نسبة الهدف", f"+{profit_at_tp:,.2f} $", f"1:{rr:.1f}"),
            "└────────────────",
            "",
            f"🔒 تعادل: <b>{be}</b>  ·  ✂️ جزئي: <b>{partial}</b>  ·  🕒 <code>{opened}</code>",
        ]
    )


def format_positions_list(
    positions: list[Position],
    prices: dict[str, float],
) -> str:
    from core.constants import score_to_percent
    from data.symbol_routing import display_symbol

    lines = [
        _header("صفقاتي المفتوحة"),
        "",
        "<i>كل زر يعرض: القوة عند الدخول + نسبة الربح/الخسارة الآن</i>",
        "",
    ]
    if not positions:
        lines.append("لا توجد صفقات مفتوحة.")
        lines.append("")
        lines.append("راقب الفرص من 📡 الإشارات")
        return "\n".join(lines)

    for pos in positions:
        current = prices.get(pos.symbol, pos.entry_price)
        if pos.side.value == "buy":
            unrealized = (current - pos.entry_price) * pos.amount
            pnl_pct = (
                ((current - pos.entry_price) / pos.entry_price) * 100
                if pos.entry_price > 0
                else 0.0
            )
            side_ar = "شراء"
        else:
            unrealized = (pos.entry_price - current) * pos.amount
            pnl_pct = (
                ((pos.entry_price - current) / pos.entry_price) * 100
                if pos.entry_price > 0
                else 0.0
            )
            side_ar = "بيع"
        sign = "+" if unrealized >= 0 else ""
        pnl_sign = "+" if pnl_pct >= 0 else ""
        icon = "🟢" if unrealized >= 0 else "🔴"
        strength = score_to_percent(pos.signal_score) if pos.signal_score > 0 else 0
        strength_txt = f"{strength}/100" if strength > 0 else "—"
        coin = escape(display_symbol(pos.symbol))
        lines.append(
            f"{icon} <b>{coin}</b>  ·  {side_ar}\n"
            f"   ⚡ قوة الدخول: <code>{escape(strength_txt)}</code>\n"
            f"   💰 الآن: <code>{sign}{unrealized:,.2f} $</code>  "
            f"(<code>{pnl_sign}{pnl_pct:.2f}%</code>)\n"
            f"   دخلت {pos.entry_price:,.2f} → الآن {current:,.2f}\n"
            f"   SL {pos.stop_loss:,.2f}  |  TP {pos.take_profit:,.2f}"
        )
        lines.append("")
    lines.append("اضغط على الصفقة لعرض التفاصيل الكاملة 👇")
    return "\n".join(lines).rstrip()


def format_action_result(title: str, detail: str) -> str:
    return "\n".join([_header(title), "", escape(detail)])
