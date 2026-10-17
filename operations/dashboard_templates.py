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
from operations.message_templates import DIVIDER, _BRAND, _money, _row, escape

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


def compute_open_floating_pnl(
    positions: list[Position],
    prices: dict[str, float],
) -> tuple[float, float]:
    """مجموع الربح/الخسارة العائم لكل المراكز + نسبة تقريبية على رأس المال المستثمر."""
    total = 0.0
    invested = 0.0
    for pos in positions:
        try:
            current = float(prices.get(pos.symbol, pos.entry_price) or pos.entry_price)
            entry = float(pos.entry_price or 0.0)
            amount = float(pos.amount or 0.0)
            if amount <= 0 or entry <= 0:
                continue
            if getattr(pos.side, "value", str(pos.side)).lower() == "buy":
                total += (current - entry) * amount
            else:
                total += (entry - current) * amount
            invested += entry * amount
        except Exception:
            continue
    pct = (total / invested * 100.0) if invested > 0 else 0.0
    return total, pct


def format_floating_pnl_banner(
    total_pnl: float,
    *,
    open_count: int = 0,
    pct: float | None = None,
    placement: str = "bottom",
) -> str:
    """شريط المجموع الكلي للعائم — أسفل قائمة المراكز المفتوحة افتراضياً."""
    if open_count <= 0:
        return (
            f"{DIVIDER}\n"
            "💹 <b>المجموع الكلي</b>\n"
            "<code>0.00 USD</code>"
        )
    icon = "🟢" if total_pnl >= 0 else "🔴"
    sign = "+" if total_pnl >= 0 else ""
    pct_line = ""
    if pct is not None:
        psign = "+" if pct >= 0 else ""
        pct_line = f"\nنسبة المحفظة: <code>{psign}{pct:.2f}%</code>"
    title = "💹 <b>المجموع الكلي (كل المراكز)</b>"
    body = (
        f"{icon} <b><code>{sign}{total_pnl:,.2f} USD</code></b>"
        f"{pct_line}\n"
        f"<i>{open_count} مركز مفتوح</i>"
    )
    if placement == "top":
        return f"{title}\n{body}"
    return f"{DIVIDER}\n{title}\n{body}"


def _fmt_px(value: float) -> str:
    """تنسيق سعر موحّد للقائمة — مريح للعين."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    abs_v = abs(v)
    if abs_v >= 1000:
        return f"{v:,.2f}"
    if abs_v >= 1:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _soft_row(icon: str, label: str, value: str) -> str:
    """سطر موحّد العرض داخل بطاقة المركز."""
    return f"{icon} {escape(label)}: <code>{escape(value)}</code>"


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
    floating_pnl: float | None = None,
) -> str:
    status = "موقوف ⏸️" if paused else "يعمل ✅"
    mode_note = "تجريبي" if mode.upper() == "PAPER" else "حقيقي"
    # النظام الهجين (قاعدة دائمة): تلقائي 9–10 | يدوي 7–8
    try:
        from config.project_rules import load_project_rules

        rules = load_project_rules()
        hybrid = bool(rules.hybrid_mode)
    except Exception:
        hybrid = True
    auto_pct = get_settings().auto_entry_min_percent
    if hybrid:
        entry_note = "هجين ⚡🖐"
        mode_hint = (
            "<i>⚡ تلقائي فقط عند قوة 9–10/10 — "
            "🖐 إشارات 7–8 تُرسل لتيليجرام للفتح اليدوي (حرية Demo).</i>"
        )
    elif auto_pct >= 100:
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
    float_val = "—"
    if floating_pnl is not None and open_count > 0:
        fsign = "+" if floating_pnl >= 0 else ""
        float_val = f"<code>{fsign}{floating_pnl:,.2f}</code> USD"
    lines = [
        _header("لوحة التحكم"),
        "",
        _row("الحالة", f"<b>{status}</b>", icon="🤖"),
        _row("الوضع", f"<b>{mode_note}</b>", icon="⚙️"),
        _row("الدخول", f"<b>{entry_note}</b>", icon="🎯"),
        DIVIDER,
        _row("الرصيد", f"<b>{_money(balance)}</b>", icon="💰"),
        _row("العائم", float_val, icon="📊"),
        _row("اليوم", f"<b>{escape(daily_pnl)}</b>", icon="📈"),
        _row("المفتوحة", f"<b>{open_count}</b>", icon="📂"),
        _row("المراقبة", f"<b>{pairs_count}</b> عملات", icon="📡"),
        "",
        mode_hint,
        "<i>📡 الإشارات · 📂 المراكز · 📜 السجل</i>",
    ]
    return "\n".join(lines)


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
        "<i>كل الأزواج — جاهزة للدخول + انتظار (WAIT) — مثل CMD</i>",
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
    interval_seconds: float | int = 0.8,
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
    try:
        iv = float(interval_seconds)
    except (TypeError, ValueError):
        iv = 0.8
    iv_label = f"{iv:.1f}" if iv < 2 else str(int(iv))
    lines = [
        _header("بث حي — الإشارات"),
        "",
        f"<i>يتحدّث تلقائياً كل ~{iv_label} ثانية — ممنوع السكون</i>",
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


def format_console_signals_board(
    all_entries: list[dict],
    *,
    interval_seconds: float | int = 0.8,
    updated_at: str = "",
) -> str:
    """لوحة إشارات لنوافذ CMD — نص صريح بدون HTML (إشارات فقط، ليست صفقات)."""
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
    try:
        iv = float(interval_seconds)
    except (TypeError, ValueError):
        iv = 0.8
    stamp = updated_at or "—"
    lines = [
        "========================================================",
        "  GoldenShield AI  |  LIVE SIGNALS",
        "  Signals only — NOT trades / NOT positions",
        "========================================================",
        f"  Updated : {stamp}",
        f"  Refresh : every ~{iv:.1f}s",
        f"  Watching: {len(ordered)}   Ready: {len(ready)}",
        "--------------------------------------------------------",
    ]
    if not ordered:
        lines.append("  (waiting for analysis cycle...)")
        lines.append("========================================================")
        return "\n".join(lines)

    for entry in ordered:
        raw_symbol = str(entry.get("symbol") or "?")
        try:
            base = display_symbol(raw_symbol)
        except Exception:
            base = raw_symbol
        base = str(base or raw_symbol or "?").strip()
        if base.upper().endswith("/USDT"):
            symbol = base
        elif "/" in base:
            symbol = base
        else:
            symbol = f"{base}/USDT"
        try:
            price = float(entry.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0
        score = int(entry.get("score", 0) or 0)
        signal = str(entry.get("signal") or "WAIT")
        if signal == "BUY SIGNAL":
            state = "BUY"
        elif signal == "SELL SIGNAL":
            state = "SELL"
        elif signal == "REJECTED":
            state = "REJECT"
        else:
            state = "WAIT"
        # نفس أسلوب القراءة القديمة في CMD
        if price >= 100:
            price_txt = f"{price:.2f}"
        elif price >= 1:
            price_txt = f"{price:.4f}"
        else:
            price_txt = f"{price:.6f}"
        lines.append(
            f"  * {symbol} | price: {price_txt} | score: {score}/10 | {state}"
        )

    lines.extend(
        [
            "--------------------------------------------------------",
            "  Auto entry from 9-10/10 only | below that = WAIT/manual",
            "========================================================",
        ]
    )
    return "\n".join(lines)


def write_console_signals_board_file(
    all_entries: list[dict],
    *,
    interval_seconds: float | int = 0.8,
    updated_at: str = "",
    path: str | None = None,
) -> str | None:
    """يكتب لوحة الإشارات لنافذة الحالة على القرص — لا يرمي استثناء للحلقة الرئيسية."""
    try:
        from pathlib import Path

        target = Path(path or "storage/runtime/signals_board.txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        text = format_console_signals_board(
            all_entries,
            interval_seconds=interval_seconds,
            updated_at=updated_at,
        )
        target.write_text(text, encoding="utf-8-sig")
        try:
            import json
            from datetime import datetime, timezone

            from terminal_app.config import RUNTIME

            pulse_rows = []
            for entry in all_entries or []:
                if not isinstance(entry, dict):
                    continue
                sym = str(entry.get("symbol") or "?").upper()
                if not sym.endswith("/USDT") and "/" not in sym:
                    sym = f"{sym}/USDT"
                pulse_rows.append(
                    {
                        "sym": sym,
                        "score": int(entry.get("score") or 0),
                        "signal": str(entry.get("signal") or "WAIT"),
                        "price": float(entry.get("price") or 0),
                    }
                )
            ts = datetime.now(timezone.utc).isoformat()
            (RUNTIME / "last_cycle_signals.json").write_text(
                json.dumps({"signals": pulse_rows, "ts": ts}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (RUNTIME / "heartbeat.json").write_text(
                json.dumps({"ts": ts, "service": "bot-cycle", "signals": len(pulse_rows)}),
                encoding="utf-8",
            )
        except Exception:
            pass
        return str(target)
    except Exception:
        return None


def _line(icon: str, label: str, value: str, extra: str = "") -> str:
    """سطر واحد منظم ومحاذي: أيقونة + تسمية ثابتة العرض + قيمة."""
    label_pad = f"{label:<8}"
    base = f"│  {icon}  <code>{escape(label_pad)}</code>  <code>{value}</code>"
    if extra:
        return f"{base}  <code>{extra}</code>"
    return base


def _position_strength_display(
    position: Position,
    *,
    live_score: int = 0,
) -> tuple[str, str]:
    """(عنوان، قيمة) لقوة الصفقة — دخول محفوظ أو قوة السوق الحالية."""
    entry = int(getattr(position, "signal_score", 0) or 0)
    live = int(live_score or 0)
    if entry > 0:
        return "قوة الدخول", f"{score_to_percent(entry)}/100"
    if live > 0:
        return "قوة السوق الآن", f"{score_to_percent(live)}/100"
    return "قوة الدخول", "—"


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
    live_score: int = 0,
) -> str:
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
    strength_label, strength_txt = _position_strength_display(
        position, live_score=live_score
    )
    sl_pct = _pct_change(position.entry_price, position.stop_loss)
    tp_pct = _pct_change(position.entry_price, position.take_profit)

    return "\n".join(
        [
            _BRAND,
            DIVIDER,
            f"<b>{coin}</b>  ·  {side_ar}  ·  {escape(mode)}",
            "",
            f"⚡  <b>{strength_label}</b>  ·  <code>{escape(strength_txt)}</code>",
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
    *,
    live_scores: dict[str, int] | None = None,
) -> str:
    from data.symbol_routing import display_symbol

    live_scores = live_scores or {}
    total_pnl, total_pct = compute_open_floating_pnl(positions, prices)
    lines = [
        _header("صفقاتي المفتوحة"),
        "",
        "<i>كل صفقة بنفس الترتيب — اضغط الزر للتفاصيل</i>",
        "",
    ]
    if not positions:
        lines.append("لا توجد صفقات مفتوحة.")
        lines.append("")
        lines.append("راقب الفرص من 📡 الإشارات")
        lines.append("")
        lines.append(
            format_floating_pnl_banner(0.0, open_count=0, pct=0.0, placement="bottom")
        )
        return "\n".join(lines)

    for idx, pos in enumerate(positions):
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
        strength_label, strength_txt = _position_strength_display(
            pos, live_score=int(live_scores.get(pos.symbol, 0) or 0)
        )
        coin = escape(display_symbol(pos.symbol))
        entry_s = _fmt_px(pos.entry_price)
        now_s = _fmt_px(current)
        sl_s = _fmt_px(pos.stop_loss)
        tp_s = _fmt_px(pos.take_profit)
        block = [
            f"{icon} <b>{coin}</b> · {side_ar}",
            _soft_row("⚡", strength_label, strength_txt),
            _soft_row("💰", "النتيجة الآن", f"{sign}{unrealized:,.2f} $  ({pnl_sign}{pnl_pct:.2f}%)"),
            _soft_row("🎯", "الدخول ← الآن", f"{entry_s}  ←  {now_s}"),
            _soft_row("🛡", "SL / TP", f"{sl_s}  |  {tp_s}"),
        ]
        lines.append("\n".join(block))
        if idx < len(positions) - 1:
            lines.append("")
            lines.append("───────────────")
            lines.append("")

    lines.append("")
    lines.append("اضغط على الصفقة لعرض التفاصيل الكاملة 👇")
    lines.append("")
    lines.append(
        format_floating_pnl_banner(
            total_pnl,
            open_count=len(positions),
            pct=total_pct,
            placement="bottom",
        )
    )
    return "\n".join(lines).rstrip()


def format_action_result(title: str, detail: str) -> str:
    return "\n".join([_header(title), "", detail if "<" in detail else escape(detail)])


def format_closed_trades_history(
    trades: list,
    *,
    summary: dict | None = None,
    limit_shown: int = 40,
) -> str:
    """سجل دائم للصفقات المغلقة (ربح/خسارة) للمراجعة والتجارب."""
    lines = [
        _header("سجل الصفقات"),
        "",
        "📦 <b>الأرشيف الدائم</b> — لا تُحذف الصفقات المغلقة",
        DIVIDER,
    ]
    if summary:
        total = float(summary.get("total_pnl", 0) or 0)
        sign = "+" if total >= 0 else ""
        lines.extend(
            [
                (
                    f"مفتوح: <b>{int(summary.get('open', 0))}</b> | "
                    f"مغلق: <b>{int(summary.get('closed', 0))}</b>"
                ),
                (
                    f"رابح: <b>{int(summary.get('wins', 0))}</b> | "
                    f"خاسر: <b>{int(summary.get('losses', 0))}</b> | "
                    f"تعادل: <b>{int(summary.get('flat', 0))}</b>"
                ),
                f"صافي المغلق: <b>{sign}{_money(total)}</b> USDT",
                DIVIDER,
            ]
        )
    if not trades:
        lines.append("لا توجد صفقات مغلقة بعد — سيظهر هنا كل إغلاق للتجربة.")
        return "\n".join(lines)

    shown = list(trades)[: max(1, int(limit_shown))]
    for idx, t in enumerate(shown, start=1):
        pnl = float(getattr(t, "pnl", 0) or 0)
        icon = "✅" if pnl > 0 else ("❌" if pnl < 0 else "➖")
        sign = "+" if pnl >= 0 else ""
        entry = float(getattr(t, "entry_price", 0) or 0)
        exit_p = getattr(t, "exit_price", None)
        exit_s = f"{float(exit_p):.4g}" if exit_p is not None else "—"
        closed_at = str(getattr(t, "closed_at", "") or "")[:16].replace("T", " ")
        symbol = escape(str(getattr(t, "symbol", "?")))
        side = escape(str(getattr(t, "side", "")))
        lines.append(
            f"{idx}. {icon} <b>{symbol}</b> {side}\n"
            f"   دخول {entry:.4g} → خروج {exit_s}\n"
            f"   PnL: <b>{sign}{_money(pnl)}</b> | {escape(closed_at)}"
        )
        if idx < len(shown):
            lines.append("")
    if len(trades) > len(shown):
        lines.append("")
        lines.append(f"… و {len(trades) - len(shown)} صفقة أخرى في قاعدة البيانات")
    lines.append("")
    lines.append("هذا السجل للمراجعة — لا يُحذف عند الإغلاق.")
    return "\n".join(lines)
