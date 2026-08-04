"""تقارير أداء بفترات زمنية — طبقة مضافة فوق سجل الصفقات."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from config.project_rules import load_project_rules
from operations.message_templates import DIVIDER, _BRAND, _money, escape


def period_bounds(kind: str) -> tuple[str, str, str]:
    """يرجع (label, from_iso, to_iso) بتوقيت UTC لليوم الشامل."""
    today = datetime.now(timezone.utc).date()
    if kind == "week":
        start = today - timedelta(days=7)
        label = "آخر 7 أيام"
    elif kind == "month":
        start = today - timedelta(days=30)
        label = "آخر 30 يوماً"
    else:
        start = today
        label = "اليوم"
    end = today + timedelta(days=1)
    return (
        label,
        datetime(start.year, start.month, start.day, tzinfo=timezone.utc).isoformat(),
        datetime(end.year, end.month, end.day, tzinfo=timezone.utc).isoformat(),
    )


def analyze_period_trades(trades: Iterable, *, label: str) -> str:
    rules = load_project_rules()
    rows = list(trades or [])
    wins = [t for t in rows if float(getattr(t, "pnl", 0) or 0) > 0]
    losses = [t for t in rows if float(getattr(t, "pnl", 0) or 0) < 0]
    flat = [t for t in rows if float(getattr(t, "pnl", 0) or 0) == 0]
    total_pnl = sum(float(getattr(t, "pnl", 0) or 0) for t in rows)
    dustish = 0
    for t in rows:
        try:
            notional = abs(float(getattr(t, "amount", 0) or 0) * float(getattr(t, "entry_price", 0) or 0))
            if notional + 1e-9 < float(rules.min_trade_notional):
                dustish += 1
        except Exception:
            pass

    win_rate = (len(wins) / len(rows) * 100.0) if rows else 0.0
    sign = "+" if total_pnl >= 0 else ""
    positives: list[str] = []
    negatives: list[str] = []
    if rows:
        positives.append(f"عدد الصفقات المسجّلة: {len(rows)}")
        positives.append(f"رابح: {len(wins)} | معدل نجاح تقريبي: {win_rate:.0f}%")
        if dustish == 0:
            positives.append(
                f"لا مخالفات غبار واضحة مقابل حد المشروع {rules.min_trade_notional:.0f}$"
            )
        else:
            negatives.append(
                f"صفقات بحجم ضعيف/غبار (~{dustish}) تحت حد {rules.min_trade_notional:.0f}$"
            )
        if losses:
            negatives.append(f"صفقات خاسرة: {len(losses)}")
            # أسوأ صفقة
            worst = min(losses, key=lambda x: float(getattr(x, "pnl", 0) or 0))
            negatives.append(
                f"أسوأ صفقة: {escape(getattr(worst, 'symbol', '?'))} "
                f"({float(getattr(worst, 'pnl', 0) or 0):+.2f})"
            )
        if wins:
            best = max(wins, key=lambda x: float(getattr(x, "pnl", 0) or 0))
            positives.append(
                f"أفضل صفقة: {escape(getattr(best, 'symbol', '?'))} "
                f"({float(getattr(best, 'pnl', 0) or 0):+.2f})"
            )
    else:
        negatives.append("لا صفقات مغلقة في هذه الفترة")

    lines = [
        f"{_BRAND}",
        DIVIDER,
        f"<i>تقرير الفترة — {escape(label)}</i>",
        "",
        f"📌 المرجع: رأس مال قواعد <code>{rules.reference_capital:,.0f}</code> USDT",
        f"صافي الفترة: <b>{sign}{_money(total_pnl)}</b>",
        f"مغلق: <b>{len(rows)}</b> | رابح <b>{len(wins)}</b> | خاسر <b>{len(losses)}</b> | تعادل <b>{len(flat)}</b>",
        "",
        "✅ <b>الإيجابيات</b>",
    ]
    lines.extend([f"• {p}" for p in positives] or ["• —"])
    lines.extend(["", "⚠️ <b>السلبيات / نقاط الضعف</b>"])
    lines.extend([f"• {n}" for n in negatives] or ["• —"])
    lines.extend(
        [
            "",
            "<i>التقرير تحليلي من سجل DB الدائم — لا يحذف صفقات.</i>",
        ]
    )
    return "\n".join(lines)
