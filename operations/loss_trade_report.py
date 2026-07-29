"""تقارير الصفقات الخاسرة — حفظ دائم + استرجاع لاحق."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR, get_settings

logger = logging.getLogger(__name__)

REPORTS_DIR = BASE_DIR / "storage" / "reports" / "losing_trades"
JSONL_PATH = REPORTS_DIR / "losing_trades.jsonl"


@dataclass
class LosingTradeReport:
    report_id: str
    created_at: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    amount: float
    pnl: float
    stop_loss: float
    take_profit: float
    exit_reason: str
    signal_score: int = 0
    risk_mode: str = "standard"
    entry_filters: str = ""
    opened_at: str = ""
    hold_minutes: float | None = None
    loss_category: str = ""
    why_lost_ar: str = ""
    contributing_factors_ar: list[str] = field(default_factory=list)
    lessons_ar: list[str] = field(default_factory=list)
    position_id: str = ""
    is_paper: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_loss(
    *,
    side: str,
    entry_price: float,
    exit_price: float,
    stop_loss: float,
    take_profit: float,
    exit_reason: str,
    signal_score: int = 0,
    entry_filters: str = "",
) -> tuple[str, str, list[str], list[str]]:
    """تصنيف سبب الخسارة + شرح عربي + عوامل + دروس."""
    reason_l = (exit_reason or "").strip().lower()
    side_l = str(side).lower()
    is_buy = side_l in {"buy", "long", "orderside.buy"}

    moved_against = (exit_price < entry_price) if is_buy else (exit_price > entry_price)
    near_sl = False
    if stop_loss > 0:
        sl_dist = abs(entry_price - stop_loss)
        if sl_dist > 0:
            near_sl = abs(exit_price - stop_loss) <= max(sl_dist * 0.15, entry_price * 0.0005)

    factors: list[str] = []
    lessons: list[str] = []

    if "stop loss" in reason_l or reason_l in {"sl", "hit_sl"}:
        category = "stop_loss"
        why = "الصفقة لمست وقف الخسارة (Stop Loss) فانغلقت لحماية رأس المال."
        factors.append("السعر تحرك ضد اتجاه الدخول حتى مستوى الـ SL.")
        lessons.append("راجع جودة نقطة الدخول وتأكيدات SMC قبل الصفقة التالية.")
    elif "emergency" in reason_l or "panic" in reason_l:
        category = "emergency"
        why = "إغلاق طارئ (Emergency/Panic) — خرجت الصفقة خاسرة بسبب قرار حماية فوري."
        factors.append("أُغلقت كل/هذه المراكز يدوياً أو تلقائياً تحت ضغط المخاطر.")
        lessons.append("راجع سبب الطوارئ (Kill Switch / Panic / انقطاع) قبل إعادة الدخول.")
    elif "trail" in reason_l or "breakeven" in reason_l:
        category = "trail_or_breakeven"
        why = "الخروج مرتبط بتتبع/نقطة تعادل، لكن النتيجة النهائية بقيت خسارة."
        factors.append(f"سبب الإغلاق المسجّل: {exit_reason}")
        lessons.append("التتبع يقلل الربح أحياناً؛ راجع إعدادات الـ trailing.")
    elif "manual" in reason_l or "لوحة" in (exit_reason or "") or "يدوي" in (exit_reason or ""):
        category = "manual"
        why = "إغلاق يدوي والصفقة كانت خاسرة وقت الإغلاق."
        factors.append("قرار بشري أنهى الصفقة قبل (أو عند) تحقق الهدف.")
        lessons.append("وثّق لماذا أغلقتها يدوياً لتفادي التكرار غير المدروس.")
    elif "take profit" in reason_l:
        category = "tp_but_negative"
        why = "سبب الإغلاق Take Profit لكن PnL سالب (جزئي/انزلاق/اتجاه معاكس)."
        factors.append("تحقق من الانزلاق أو الإغلاق الجزئي المتعدد.")
        lessons.append("راجع مسار الخروج متعدد المستويات (exit tiers).")
    elif near_sl:
        category = "near_stop_loss"
        why = "السعر أغلق قرب وقف الخسارة؛ الخسارة ناتجة عن كسر مستوى الحماية."
        factors.append("المسافة بين سعر الخروج والـ SL صغيرة نسبياً.")
        lessons.append("قد يكون هناك صيد سيولة (Stop Hunt) — راجع الفلاتر.")
    elif moved_against:
        category = "adverse_move"
        why = f"السعر تحرك ضد الصفقة. سبب الإغلاق المسجّل: {exit_reason or 'غير محدد'}."
        factors.append("الاتجاه الفعلي خالف فرضية الدخول.")
        lessons.append("ارفع عتبة الدخول أو فعّل فلاتر اتجاه أقوى (ADX/Kill Zones).")
    else:
        category = "other"
        why = f"صفقة خاسرة. سبب الإغلاق: {exit_reason or 'غير محدد'}."
        factors.append("لم يُصنَّف السبب تلقائياً بدقة كافية.")
        lessons.append("راجع لقطة التدقيق والسجل حول وقت الإغلاق.")

    if signal_score and signal_score < 7:
        factors.append(f"درجة الإشارة عند الدخول كانت منخفضة نسبياً ({signal_score}/10).")
        lessons.append("فضّل الدخول عند درجات أعلى (≥ عتبة الضمان).")

    filters = (entry_filters or "").strip()
    if filters:
        factors.append(f"سياق الدخول/الفلاتر: {filters[:240]}")

    if stop_loss <= 0:
        factors.append("تحذير: وقف الخسارة غير مضبوط بشكل واضح على السجل.")
        lessons.append("تأكد أن Zero-SL denial و Emergency ATR يعملان.")

    return category, why, factors, lessons


def build_losing_trade_report(
    *,
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    amount: float,
    pnl: float,
    stop_loss: float,
    take_profit: float,
    exit_reason: str,
    signal_score: int = 0,
    risk_mode: str = "standard",
    entry_filters: str = "",
    opened_at: str | datetime | None = None,
    position_id: str = "",
    is_paper: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> LosingTradeReport:
    opened_s = ""
    hold_minutes: float | None = None
    if isinstance(opened_at, datetime):
        opened_s = opened_at.astimezone(timezone.utc).isoformat()
        hold_minutes = (datetime.now(timezone.utc) - opened_at.astimezone(timezone.utc)).total_seconds() / 60.0
    elif opened_at:
        opened_s = str(opened_at)
        try:
            parsed = datetime.fromisoformat(opened_s.replace("Z", "+00:00"))
            hold_minutes = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 60.0
        except ValueError:
            hold_minutes = None

    category, why, factors, lessons = classify_loss(
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        exit_reason=exit_reason,
        signal_score=signal_score,
        entry_filters=entry_filters,
    )

    settings = get_settings()
    paper = bool(settings.execution_mode == "paper") if is_paper is None else bool(is_paper)

    return LosingTradeReport(
        report_id=uuid.uuid4().hex[:12],
        created_at=_utc_now_iso(),
        symbol=symbol,
        side=str(side),
        entry_price=float(entry_price),
        exit_price=float(exit_price),
        amount=float(amount),
        pnl=float(pnl),
        stop_loss=float(stop_loss or 0.0),
        take_profit=float(take_profit or 0.0),
        exit_reason=str(exit_reason or ""),
        signal_score=int(signal_score or 0),
        risk_mode=str(risk_mode or "standard"),
        entry_filters=str(entry_filters or ""),
        opened_at=opened_s,
        hold_minutes=round(hold_minutes, 2) if hold_minutes is not None else None,
        loss_category=category,
        why_lost_ar=why,
        contributing_factors_ar=factors,
        lessons_ar=lessons,
        position_id=str(position_id or ""),
        is_paper=paper,
        extra=extra or {},
    )


def save_losing_trade_report(report: LosingTradeReport) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    # ملف فردي
    single = REPORTS_DIR / f"{report.created_at[:10]}_{report.symbol.replace('/', '-')}_{report.report_id}.json"
    single.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # سجل تراكمي
    with JSONL_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    logger.info(
        "حفظ تقرير خسارة %s | %s | PnL=%.2f | %s",
        report.report_id,
        report.symbol,
        report.pnl,
        report.loss_category,
    )
    return single


def record_losing_trade_from_position(
    position: Any,
    *,
    exit_price: float,
    pnl: float,
    reason: str,
) -> LosingTradeReport | None:
    """يُستدعى عند إغلاق صفقة خاسرة — لا يرمي استثناء للخارج."""
    try:
        if float(pnl) >= 0:
            return None
        report = build_losing_trade_report(
            symbol=str(position.symbol),
            side=str(position.side),
            entry_price=float(position.entry_price),
            exit_price=float(exit_price),
            amount=float(position.amount),
            pnl=float(pnl),
            stop_loss=float(getattr(position, "stop_loss", 0.0) or 0.0),
            take_profit=float(getattr(position, "take_profit", 0.0) or 0.0),
            exit_reason=reason,
            signal_score=int(getattr(position, "signal_score", 0) or 0),
            risk_mode=str(getattr(position, "risk_mode", "standard") or "standard"),
            entry_filters=str(getattr(position, "entry_filters", "") or ""),
            opened_at=getattr(position, "opened_at", None),
            position_id=str(getattr(position, "id", "") or ""),
            is_paper=bool(getattr(position, "is_paper", True)),
        )
        save_losing_trade_report(report)
        return report
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_losing_trade_from_position فشل: %s", exc)
        return None


def load_losing_trade_reports(*, limit: int = 50) -> list[dict[str, Any]]:
    if not JSONL_PATH.exists():
        # fallback: individual json files
        if not REPORTS_DIR.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
            if len(rows) >= limit:
                break
        return rows

    lines = JSONL_PATH.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(rows) >= limit:
            break
    return rows


def format_losing_trade_report_telegram(report: LosingTradeReport | dict[str, Any]) -> str:
    data = asdict(report) if isinstance(report, LosingTradeReport) else dict(report)
    factors = data.get("contributing_factors_ar") or []
    lessons = data.get("lessons_ar") or []
    hold = data.get("hold_minutes")
    hold_txt = f"{hold:.1f} د" if isinstance(hold, (int, float)) else "—"
    side = str(data.get("side", ""))
    side_ar = "شراء" if "buy" in side.lower() else "بيع"
    lines = [
        f"📉 <b>تقرير صفقة خاسرة</b> — <code>{data.get('symbol')}</code>",
        f"المعرّف: <code>{data.get('report_id')}</code>",
        f"الاتجاه: {side_ar}",
        f"الدخول: {float(data.get('entry_price', 0)):.5f} → الخروج: {float(data.get('exit_price', 0)):.5f}",
        f"PnL: <b>{float(data.get('pnl', 0)):.2f}</b>",
        f"سبب الإغلاق: {data.get('exit_reason') or '—'}",
        f"التصنيف: <code>{data.get('loss_category') or '—'}</code>",
        f"مدة الصفقة: {hold_txt}",
        f"درجة الإشارة: {data.get('signal_score', 0)}/10",
        "",
        f"<b>لماذا خسرت؟</b>\n{data.get('why_lost_ar') or '—'}",
    ]
    if factors:
        lines.append("")
        lines.append("<b>عوامل مساهمة:</b>")
        lines.extend(f"• {f}" for f in factors[:6])
    if lessons:
        lines.append("")
        lines.append("<b>دروس:</b>")
        lines.extend(f"• {x}" for x in lessons[:4])
    return "\n".join(lines)


def format_losing_trades_digest(reports: list[dict[str, Any]], *, limit: int = 10) -> str:
    if not reports:
        return (
            "📭 <b>لا توجد تقارير صفقات خاسرة محفوظة بعد.</b>\n"
            "عند إغلاق أي صفقة بخسارة سيُحفظ تقرير تلقائياً هنا."
        )
    lines = [f"📉 <b>آخر {min(limit, len(reports))} صفقة خاسرة</b>", ""]
    for i, row in enumerate(reports[:limit], start=1):
        lines.append(
            f"{i}) <code>{row.get('symbol')}</code> | PnL {float(row.get('pnl', 0)):.2f} | "
            f"{row.get('loss_category') or '—'} | {row.get('exit_reason') or '—'}"
        )
        why = str(row.get("why_lost_ar") or "")[:120]
        if why:
            lines.append(f"   └ {why}")
        lines.append("")
    lines.append("للتفاصيل: <b>/loss_detail رمز</b> أو اطلب من المساعد عرض التقارير.")
    return "\n".join(lines).strip()


def find_reports_for_symbol(symbol: str, *, limit: int = 5) -> list[dict[str, Any]]:
    sym = symbol.strip().upper()
    rows = load_losing_trade_reports(limit=200)
    matched = [r for r in rows if str(r.get("symbol", "")).upper() == sym]
    return matched[:limit]
