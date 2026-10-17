"""أرشيف عمل البوت مرتباً بالشهر — تقارير + أحداث + حزمة مراجعة."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = Path("storage") / "reports"


def _archive_enabled() -> bool:
    raw = os.getenv("REPORT_FILE_ARCHIVE_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _activity_enabled() -> bool:
    raw = os.getenv("BOT_ACTIVITY_ARCHIVE_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def reports_root() -> Path:
    raw = (os.getenv("REPORT_ARCHIVE_DIR") or "").strip()
    return Path(raw) if raw else _DEFAULT_ROOT


def month_dir(report_date: date | None = None) -> Path:
    d = report_date or date.today()
    return reports_root() / f"{d.year:04d}-{d.month:02d}"


def report_file_path(report_date: date | None = None) -> Path:
    d = report_date or date.today()
    return month_dir(d) / f"{d.isoformat()}.txt"


def activity_file_path(report_date: date | None = None) -> Path:
    d = report_date or date.today()
    return month_dir(d) / "bot_activity.jsonl"


def save_daily_report_file(content: str, report_date: date | None = None) -> Path | None:
    """يحفظ تقرير اليوم في storage/reports/YYYY-MM/YYYY-MM-DD.txt."""
    if not _archive_enabled():
        return None
    try:
        d = report_date or date.today()
        path = report_file_path(d)
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = content if content.endswith("\n") else content + "\n"
        header = (
            f"# GoldenShield daily report\n"
            f"# date={d.isoformat()}\n"
            f"# archived_at={stamp}\n"
            f"# ---\n\n"
        )
        path.write_text(header + body, encoding="utf-8")
        log_bot_activity("daily_report_saved", report_date=d.isoformat(), chars=len(content))
        return path
    except Exception:
        logger.exception("فشل أرشفة ملف التقرير اليومي")
        return None


def log_bot_activity(event: str, **fields: Any) -> None:
    """يسجّل حدث تشغيل في أرشيف الشهر (صفقات/أخطاء/تشغيل) — لا يوقف البوت عند الفشل."""
    if not _activity_enabled():
        return
    try:
        report_date_raw = fields.pop("report_date", None)
        report_day: date | None = None
        if isinstance(report_date_raw, date):
            report_day = report_date_raw
        elif isinstance(report_date_raw, str) and report_date_raw.strip():
            try:
                report_day = date.fromisoformat(report_date_raw.strip()[:10])
            except ValueError:
                report_day = None
        path = activity_file_path(report_day)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **{k: v for k, v in fields.items() if v is not None},
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        logger.exception("فشل كتابة bot_activity")


def list_month_reports(year: int, month: int) -> list[Path]:
    try:
        folder = reports_root() / f"{year:04d}-{month:02d}"
        if not folder.is_dir():
            return []
        return sorted(folder.glob("????-??-??.txt"))
    except Exception:
        logger.exception("فشل قراءة أرشيف الشهر %04d-%02d", year, month)
        return []


def _load_activity(year: int, month: int) -> list[dict[str, Any]]:
    path = reports_root() / f"{year:04d}-{month:02d}" / "bot_activity.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        logger.exception("فشل قراءة bot_activity")
    return rows


def summarize_activity(year: int, month: int) -> dict[str, Any]:
    rows = _load_activity(year, month)
    counts = Counter(str(r.get("event", "unknown")) for r in rows)
    opens = [r for r in rows if r.get("event") == "trade_open"]
    closes = [r for r in rows if r.get("event") == "trade_close"]
    errors = [r for r in rows if r.get("event") in {"error", "operation_error"}]
    pnl_vals = []
    for r in closes:
        try:
            pnl_vals.append(float(r.get("pnl", 0) or 0))
        except (TypeError, ValueError):
            continue
    return {
        "events_total": len(rows),
        "by_event": dict(counts),
        "trade_opens": len(opens),
        "trade_closes": len(closes),
        "errors": len(errors),
        "closed_pnl_sum": round(sum(pnl_vals), 4) if pnl_vals else 0.0,
        "symbols_opened": sorted({str(r.get("symbol")) for r in opens if r.get("symbol")}),
    }


def read_month_bundle(year: int, month: int) -> str:
    files = list_month_reports(year, month)
    summary = summarize_activity(year, month)
    parts: list[str] = [
        f"=== أرشيف GoldenShield {year:04d}-{month:02d} ===\n",
        f"أيام بتقارير: {len(files)}\n",
        f"ملخص النشاط: {json.dumps(summary, ensure_ascii=False)}\n",
    ]
    if not files and summary["events_total"] == 0:
        parts.append("لا توجد بيانات مؤرشفة لهذا الشهر بعد.\n")
        return "".join(parts)
    for path in files:
        try:
            parts.append(f"\n----- {path.name} -----\n")
            parts.append(path.read_text(encoding="utf-8"))
        except Exception as exc:
            parts.append(f"\n----- {path.name} (تعذّر القراءة: {exc}) -----\n")
    return "".join(parts)


def build_monthly_review_pack(year: int, month: int) -> Path | None:
    """ينشئ ملف مراجعة شهرية جاهز لسؤالك: إيجابيات/سلبيات/احذف/أضف."""
    if not _archive_enabled() and not _activity_enabled():
        return None
    try:
        folder = reports_root() / f"{year:04d}-{month:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        summary = summarize_activity(year, month)
        reports = list_month_reports(year, month)
        path = folder / "MONTHLY_REVIEW_PACK.md"
        lines = [
            f"# مراجعة شهرية GoldenShield — {year:04d}-{month:02d}",
            "",
            "## كيف تسأل المساعد",
            f"اكتب: **افحص شهر {month} {year}**",
            "واطلب: الإيجابيات، السلبيات، ماذا أحذف، ماذا أضيف.",
            "",
            "## ملخص آلي",
            f"- عدد أيام بتقارير يومية: **{len(reports)}**",
            f"- إجمالي أحداث مسجّلة: **{summary['events_total']}**",
            f"- فتح صفقات: **{summary['trade_opens']}**",
            f"- إغلاق صفقات: **{summary['trade_closes']}**",
            f"- مجموع PnL المغلق (من السجل): **{summary['closed_pnl_sum']}**",
            f"- أخطاء مسجّلة: **{summary['errors']}**",
            f"- رموز فُتحت: {', '.join(summary['symbols_opened']) or '—'}",
            f"- تفصيل الأحداث: `{json.dumps(summary['by_event'], ensure_ascii=False)}`",
            "",
            "## ملفات هذا الشهر",
            f"- تقارير: `{year:04d}-{month:02d}/YYYY-MM-DD.txt`",
            f"- نشاط البوت: `bot_activity.jsonl`",
            f"- قاعدة البيانات: جدول `daily_reports` + `trades` + `decision_records`",
            "",
            "## قالب قرار (يملأه المساعد عند الفحص)",
            "### الإيجابيات",
            "- ",
            "### السلبيات",
            "- ",
            "### يُحذف / يُعطَّل",
            "- ",
            "### يُضاف (طبقة واحدة فقط إن لزم)",
            "- ",
            "### القرار للشهر القادم",
            "- الإبقاء على الإعدادات / تبسيط / إصلاح أعطال فقط",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
    except Exception:
        logger.exception("فشل بناء حزمة المراجعة الشهرية")
        return None


def ensure_archive_started(start: date | None = None) -> Path | None:
    """يضع علامة أن الأرشيف يبدأ من تاريخ معيّن (اليوم افتراضياً)."""
    try:
        d = start or date.today()
        folder = month_dir(d)
        folder.mkdir(parents=True, exist_ok=True)
        marker = folder / "ARCHIVE_START.txt"
        if not marker.exists():
            marker.write_text(
                (
                    f"أرشيف عمل البوت بدأ من {d.isoformat()}.\n"
                    f"يشمل: تقارير يومية + صفقات + أحداث تشغيل/أخطاء.\n"
                    f"عند نهاية الشهر اطلب: افحص شهر {d.month} {d.year}\n"
                    f"واسأل عن: الإيجابيات، السلبيات، ماذا أحذف، ماذا أضيف.\n"
                ),
                encoding="utf-8",
            )
        guide = folder / "HOW_TO_ASK.txt"
        if not guide.exists():
            guide.write_text(
                (
                    "مثال الرسالة للمساعد:\n"
                    f"افحص شهر {d.month} {d.year}\n"
                    "أريد: إيجابيات المشروع، سلبياته، ماذا أحذف، ماذا أضيف، وهل نكمّل بنفس القواعد.\n"
                ),
                encoding="utf-8",
            )
        day_file = report_file_path(d)
        if not day_file.exists():
            save_daily_report_file(
                (
                    "خط أساس الأرشيف — بدء تسجيل عمل البوت من هذا اليوم.\n"
                    "سيُحدَّث تلقائياً عند التقرير اليومي، وتُسجَّل الصفقات في bot_activity.jsonl.\n"
                ),
                report_date=d,
            )
        log_bot_activity("archive_started", report_date=d.isoformat())
        build_monthly_review_pack(d.year, d.month)
        return folder
    except Exception:
        logger.exception("فشل تهيئة مجلد أرشيف التقارير")
        return None
