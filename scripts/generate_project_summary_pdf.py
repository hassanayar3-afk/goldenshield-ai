# -*- coding: utf-8 -*-
"""ملخص GoldenShield AI بنقاط — PDF عربي + إرسال تيليجرام."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_PATH = ROOT / "storage" / "reports" / "GoldenShield_Summary_2026-07-16.pdf"
BUILD_TAG = "2026-07-16-complete"
REPORT_DATE = "2026-07-16"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _find_arabic_font() -> Path:
    for p in (
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\tahoma.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ):
        if p.exists():
            return p
    raise FileNotFoundError("No Arabic font found.")


def _ar(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def generate_pdf(out_path: Path | None = None) -> Path:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    out = Path(out_path) if out_path else OUT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    font = _find_arabic_font()
    pdf.add_font("Arabic", "", str(font))
    pdf.add_font("Arabic", "B", str(font))
    w = pdf.w - pdf.l_margin - pdf.r_margin

    def line(text: str, size: int = 11, bold: bool = False, h: float = 7) -> None:
        pdf.set_font("Arabic", "B" if bold else "", size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, h, _ar(text), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def h(title: str) -> None:
        pdf.ln(2)
        line(title, size=14, bold=True, h=9)
        pdf.ln(1)

    def bullets(items: list[str], size: int = 10) -> None:
        for item in items:
            line(f"• {item}", size=size, h=6.5)
        pdf.ln(1)

    # غلاف
    line("GoldenShield AI", size=20, bold=True, h=12)
    line("ملخص المشروع — بنقاط", size=15, bold=True, h=10)
    line(f"التاريخ: {REPORT_DATE}  |  البناء: {BUILD_TAG}", size=11)
    line("الحالة: مكتمل 100% — الإصدار v1", size=11, bold=True)
    pdf.ln(3)

    h("1) ما هو المشروع؟")
    bullets(
        [
            "نظام تداول آلي هجين: تحليل فني SMC/FVG + ذكاء سوقي",
            "يدمج: أخبار، VIX، مشاعر، سيولة، حيتان",
            "درع مخاطر: 1% لكل صفقة · Kill Switch −3%",
            "يُدار من تيليجرام · يعمل على Contabo (paper) وWindows/Binance (Demo أو Live)",
        ]
    )

    h("2) ما اكتمل 100%")
    bullets(
        [
            "المراحل 1–9: إعدادات، بيانات، تحليل، هجين، تنفيذ، مخاطر، ظل، تيليجرام، قاعدة بيانات",
            "المرحلة 11: Docker، Contabo 24/7، CI، حزمة Windows",
            "تنفيذ Binance + استعادة مراكز بعد إعادة التشغيل",
            "واجهة تيليجرام عربية + قوائم صفقات بأيقونات",
            "بروتوكولات التشغيل المؤسسية (HC + Standard/Bonus) مدمجة برمجياً",
        ]
    )

    h("3) قواعد التشغيل الحالية")
    bullets(
        [
            "عرض الإشارات: من 75/100 فما فوق",
            "الدخول التلقائي: من 90/100 فقط (درجة 9 أو 10)",
            "75–89: يدوي فقط — بدون فتح تلقائي",
            "مخاطرة افتراضية: 1% لكل صفقة",
            "حد المراكز: حتى 12 صفقة متزامنة",
            "TELEGRAM_SIGNALS_ONLY: إشارات أساسية بدون سبام",
        ]
    )

    h("4) البروتوكولات الاختيارية (معطّلة افتراضياً)")
    bullets(
        [
            "HIGH_CONVICTION_MODE=false — وضع 3% Risk بشروط صارمة",
            "STANDARD_BONUS_PROFILE=false — ملحق حساب Standard/Bonus",
            "تفعيلهما عبر .env فقط — لا يغيّران السلوك الافتراضي",
        ]
    )

    h("5) ماذا أُضيف مؤخراً")
    bullets(
        [
            "قوائم صفقات بأيقونات عمودية (أضعف إلى أقوى)",
            "تجميع «صفقات فُتحت» في رسالة واحدة",
            "تقليل تأخير أزرار التيليجرام",
            "حفظ قوة الإشارة ورمز risk_mode على كل صفقة",
            "وثيقة إكمال رسمية: docs/PROJECT_COMPLETION_STATUS.md",
        ]
    )

    h("6) خارج نطاق v1 (مؤجّل)")
    bullets(
        [
            "مرحلة 10: منصة SaaS للعملاء — بعد شهر التجربة",
            "مرحلة 12: ذكاء متقدم RL/Regime — بعد بيانات كافية",
        ]
    )

    h("7) التشغيل السريع")
    bullets(
        [
            "Windows: استخرج ZIP إلى C:\\GoldenShield_Binance → 00_START.bat",
            "Contabo: docker compose up -d (paper 24/7)",
            "لا تشغّل محلياً وعلى السحابة لنفس الحساب معاً",
        ]
    )

    h("8) الخلاصة")
    bullets(
        [
            "GoldenShield v1 مكتمل 100% لكل ما وصلنا إليه",
            "جاهز لتجربة Binance Demo على Windows",
            "الخطوة التالية: شهر تقييم live ثم قرار SaaS أو ذكاء متقدم",
        ]
    )

    line("— نهاية الملخص —", size=11, bold=True)
    pdf.output(str(out))
    return out


def send_telegram(pdf_path: Path) -> dict:
    import requests

    _load_dotenv()
    token = os.environ.get("TELEGRAM_TOKEN") or ""
    chat = os.environ.get("TELEGRAM_CHAT_ID") or ""
    if not token or not chat:
        raise RuntimeError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")

    with pdf_path.open("rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={
                "chat_id": chat,
                "caption": (
                    "ملخص GoldenShield AI — بنقاط\n"
                    f"v1 مكتمل 100% | البناء: {BUILD_TAG}"
                ),
            },
            files={"document": (pdf_path.name, f, "application/pdf")},
            timeout=120,
        )
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram failed: {data}")
    return data


def main() -> int:
    path = generate_pdf()
    print("PDF", path, path.stat().st_size)
    data = send_telegram(path)
    print("TELEGRAM ok", data.get("ok"), "msg", (data.get("result") or {}).get("message_id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
