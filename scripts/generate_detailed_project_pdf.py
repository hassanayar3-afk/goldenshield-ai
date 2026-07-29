# -*- coding: utf-8 -*-
"""تقرير GoldenShield AI التفصيلي — نقاط + شرح كامل + إرسال تيليجرام."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_PATH = ROOT / "storage" / "reports" / "GoldenShield_Detailed_Report_v1.pdf"
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

    def line(text: str, size: int = 11, bold: bool = False, h: float = 6.5) -> None:
        pdf.set_font("Arabic", "B" if bold else "", size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, h, _ar(text), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def h1(title: str) -> None:
        pdf.ln(3)
        line(title, size=14, bold=True, h=9)
        pdf.ln(1)

    def h2(title: str) -> None:
        pdf.ln(1)
        line(title, size=12, bold=True, h=7.5)
        pdf.ln(0.5)

    def bullet(text: str, size: int = 10) -> None:
        line(f"• {text}", size=size, h=6.2)

    def explain(text: str, size: int = 9) -> None:
        line(f"  {text}", size=size, h=5.8)

    def section(title: str, point: str, details: list[str]) -> None:
        h2(title)
        bullet(point, size=11)
        for d in details:
            explain(d)

    # ——— غلاف ———
    line("GoldenShield AI", size=20, bold=True, h=12)
    line("التقرير التفصيلي للمشروع — حتى ما وصلنا إليه حالياً", size=13, bold=True, h=9)
    line("ملخص بنقاط + شرح تفصيلي كامل لكل بند", size=11)
    line(f"التاريخ: {REPORT_DATE}  |  البناء: {BUILD_TAG}", size=11)
    line("الحالة: الإصدار v1 مكتمل 100%", size=11, bold=True)
    pdf.ln(2)

    # ——— 1 ———
    h1("1) تعريف المشروع والرؤية")
    section(
        "1.1 ما هو GoldenShield؟",
        "نظام تداول آلي هجين يحمي رأس المال أولاً ثم ينفّذ بدقة عالية.",
        [
            "يجمع بين التحليل الفني (SMC/FVG) والذكاء السوقي (أخبار، VIX، مشاعر، سيولة).",
            "ليس مجرد بوت إشارات: فيه درع مخاطر، ظل قرار، تنفيذ، تيليجرام، وقاعدة بيانات.",
            "الهدف التشغيلي: فرص عالية الجودة فقط، مع تقليل الضوضاء والتدخل العاطفي.",
        ],
    )
    section(
        "1.2 قرار التنفيذ الحي",
        "التداول الحقيقي عبر XM + MetaTrader 5 على Windows.",
        [
            "Binance/ccxt يُستخدم كمصدر بيانات وتحليل ووضع paper.",
            "التنفيذ الحي يتم عبر جسر MT5 على ويندوز (مكتبة MT5 لا تعمل على Linux).",
            "Contabo يبقى paper 24/7 للتحليل المستمر دون أوامر XM من السحابة.",
        ],
    )

    # ——— 2 ———
    h1("2) المعمارية التشغيلية")
    section(
        "2.1 مساران متوازيان",
        "Contabo paper + Windows live يعملان معاً بأدوار مختلفة.",
        [
            "Contabo Linux: حاوية Docker، تحليل مستمر، إشعارات تيليجرام حسب الإعداد.",
            "Windows VPS: MT5 مفتوح + 00_START.bat + تنفيذ صفقات XM الحقيقية.",
            "لا يُنصح بتشغيل نسختين على نفس الحساب في نفس الوقت لتفادي تضارب الإشعارات.",
        ],
    )
    section(
        "2.2 تدفق القرار",
        "كل صفقة تمر بسلسلة فلاتر قبل التنفيذ.",
        [
            "1) جلب بيانات السوق (شموع/أسعار).",
            "2) تحليل فني متعدد الأطر M15/H1/H4.",
            "3) ذكاء هجين + إيقاف سوق عند الأخبار/الاضطراب.",
            "4) Shadow Consensus (ظل القرار).",
            "5) بوابة المخاطر (حجم الصفقة وحدود الحساب).",
            "6) التنفيذ (paper أو MT5) ثم تنبيه تيليجرام وحفظ في SQLite.",
        ],
    )

    # ——— 3 ———
    h1("3) المراحل المكتملة (1–9 + 11)")
    section(
        "المرحلة 1 — الأساسيات",
        "هيكل المشروع والإعدادات ونقطة الدخول.",
        [
            "config/settings.py + ملفات YAML للأزواج والمخاطر والتنفيذ.",
            "بيئات: dev / staging / production.",
            "main.py حلقة async + .env.example + اختبارات.",
            "لا أسرار داخل Git — كل المفاتيح في .env فقط.",
        ],
    )
    section(
        "المرحلة 2 — طبقة البيانات",
        "جلب موحّد لبيانات السوق مع مراقبة الاتصال.",
        [
            "OHLCV وTicker وOrderbook وVolume Profile وCache.",
            "مراقبة heartbeat لانقطاع الاتصال.",
            "امتداد بيانات MT5 للرموز الحية (فوركس/معادن).",
        ],
    )
    section(
        "المرحلة 3 — التحليل الفني",
        "محرك قرار فني بدرجة من 1 إلى 10.",
        [
            "SMC: BOS/CHoCH/Order Blocks + كشف FVG.",
            "توافق الأطر الزمنية: لا دخول قوي بدون محاذاة الاتجاه.",
            "Signal Scorer: 8→75% · 9→90% · 10→100%.",
            "فلاتر سبريد وتلاعب لحماية جودة الدخول.",
        ],
    )
    section(
        "المرحلة 4 — الذكاء الهجين",
        "دمج فني + أساسي + مشاعر + كلي + سيولة.",
        [
            "فلتر أخبار High Impact + مراقبة VIX والسندات.",
            "Fear & Greed وشذوذ المشاعر.",
            "تتبع الحيتان والمناطق المؤسساتية.",
            "Market Halt يوقف التداول عند اضطراب السوق.",
        ],
    )
    section(
        "المرحلة 5 — محرك التنفيذ",
        "تحويل الإشارة المعتمدة إلى أوامر ومراكز.",
        [
            "إدارة أوامر ومراكز + SL/TP + Breakeven + Emergency Flat.",
            "Mutex وCorrelation لمنع تضارب الأزواج.",
            "جسر mt5_bridge.py وخريطة رموز XM.",
            "أصول مدعومة: كريبتو + ذهب XAU + فضة XAG + نفط USOIL.",
        ],
    )
    section(
        "المرحلة 6 — إدارة المخاطر",
        "بوابة إلزامية قبل كل صفقة.",
        [
            "مخاطرة افتراضية 1% من الرصيد.",
            "Kill Switch عند −3% يومياً.",
            "راحة 24 ساعة بعد 3 خسائر متتالية.",
            "Monte Carlo + حدود يومية + استمرارية حالة المخاطر في DB.",
        ],
    )
    section(
        "المرحلة 7 — التدقيق والظل",
        "شفافية القرار قبل التنفيذ الحقيقي.",
        [
            "Snapshot لكل قرار + Decision Logger.",
            "Shadow Executor: فحص فني + سيولة.",
            "Consensus Gate: لا تنفيذ بدون توافق الظل.",
        ],
    )
    section(
        "المرحلة 8 — التشغيل وتيليجرام",
        "واجهة الإنسان الكاملة للسيطرة والمراقبة.",
        [
            "أوامر: status / panic / pause / resume / report / market / positions.",
            "لوحة عربية + أزرار + قوائم digests بأيقونات عمودية.",
            "TELEGRAM_SIGNALS_ONLY لتقليل الضوضاء.",
            "رد فوري على الأزرار + long-poll لتقليل التأخير.",
            "تجميع «صفقات فُتحت» في رسالة واحدة مرتبة أضعف→أقوى.",
        ],
    )
    section(
        "المرحلة 9 — قاعدة البيانات",
        "ذاكرة دائمة للصفقات والقرارات.",
        [
            "SQLite + migrations + repositories.",
            "نسخ احتياطي محلي + أرشيف تيليجرام.",
            "استعادة المراكز المفتوحة بعد إعادة التشغيل.",
            "أعمدة signal_score و risk_mode على الصفقات.",
        ],
    )
    section(
        "المرحلة 11 — النشر والإنتاج",
        "تشغيل 24/7 واستقرار الإنتاج.",
        [
            "Docker + Compose إنتاجي + Contabo paper.",
            "healthcheck وnginx وCI workflows.",
            "حزمة Windows: 00_START.bat / STOP / Autostart.",
            "دليل MT5_WINDOWS_SETUP.md.",
        ],
    )

    # ——— 4 ———
    h1("4) قواعد التشغيل الحالية (الأهم)")
    section(
        "4.1 عتبات الدخول",
        "عرض من 75 · تلقائي من 90 فقط.",
        [
            "75–89: تظهر يدوياً في التيليجرام — بدون فتح تلقائي.",
            "90 و100: مؤهلة للدخول التلقائي (درجة 9 أو 10).",
            "الهدف: تقليل الصفقات الضعيفة ورفع جودة التنفيذ.",
        ],
    )
    section(
        "4.2 حدود الحساب",
        "حماية رأس المال قبل الربح.",
        [
            "مخاطرة صفقة: 1% افتراضياً.",
            "حد مراكز متزامنة: حتى 12.",
            "Kill Switch −3% يومي · راحة بعد 3 خسائر.",
        ],
    )
    section(
        "4.3 وضع التيليجرام",
        "إشارات أساسية فقط بدون سبام.",
        [
            "TELEGRAM_SIGNALS_ONLY=true.",
            "قوائم جاهزة للدخول + صفقات فُتحت + إغلاق + طوارئ.",
            "لا نبضات «لا فرص» ولا بطاقات ضعيفة متكررة.",
        ],
    )

    # ——— 5 ———
    h1("5) بروتوكولات التشغيل المؤسسية")
    section(
        "5.1 بروتوكول High Conviction (3% Risk)",
        "وضع خاص للمخاطرة العالية — ليس الإعداد الافتراضي.",
        [
            "يُفعّل فقط بـ HIGH_CONVICTION_MODE=true.",
            "يشترط توافق M15/H1/H4 كامل + خبر بعيد 30 دقيقة + سيولة مؤسساتية.",
            "دخول تدريجي: 1% أولاً ثم 2% بعد التحرك لصالح الصفقة.",
            "سقف يومي، فترة تبريد، منع بعد خسارة مباشرة، فلتر جلسة السيولة.",
            "كل صفقة تُوسم risk_mode=high_conviction في قاعدة البيانات.",
        ],
    )
    section(
        "5.2 ملحق Standard / Bonus",
        "تكييف النظام مع حسابات السبريد الأعلى والبونص.",
        [
            "يُفعّل بـ STANDARD_BONUS_PROFILE=true.",
            "رفع Take Profit بنسبة 20% تقريباً لتغطية السبريد.",
            "فلتر تكلفة التنفيذ: منع الصفقة إذا التهمت التكلفة الربح المتوقع.",
            "البونص يُستخدم كهامش فقط — المخاطرة من رأس المال الحقيقي.",
        ],
    )
    section(
        "5.3 أين يعيش الكود؟",
        "مدمج في نقاط القرار الصحيحة وليس عشوائياً.",
        [
            "config/high_conviction_protocol.yaml و standard_bonus_profile.yaml.",
            "risk/high_conviction_protocol.py و standard_bonus_profile.py.",
            "main.py يمرّر prefs وprotocol إلى المخاطر والتنفيذ.",
            "الوثيقة: docs/EXECUTION_PROTOCOLS_AR.md.",
        ],
    )

    # ——— 6 ———
    h1("6) ما أُضيف في يوليو 2026")
    section(
        "6.1 واجهة وتنبيهات",
        "تجربة مستخدم أوضح وأقل إزعاجاً.",
        [
            "قوائم بأيقونات بدل جداول monospace الصلبة.",
            "ترتيب منهجي من الأضعف إلى الأقوى.",
            "تجميع الصفقات المفتوحة في digest واحد.",
            "تحسين استجابة أزرار التيليجرام.",
        ],
    )
    section(
        "6.2 أصول وتنفيذ",
        "توسيع السوق ودعم الوسيط.",
        [
            "ذهب/فضة/نفط عبر FOREX/XAUUSD وXAGUSD وUSOIL.",
            "خريطة رموز MT5: GOLD / SILVER / USOIL.",
            "حفظ قوة الإشارة على المراكز لاستعراضها لاحقاً.",
        ],
    )
    section(
        "6.3 حوكمة المشروع",
        "توثيق الإكمال الرسمي.",
        [
            "docs/PROJECT_COMPLETION_STATUS.md — حالة الإكمال 100%.",
            "SESSION_STATE.md محدّث · BUILD_TAG=2026-07-16-complete.",
            "فهرس التخطيط محدّث في GoldenShield_AI_Planning.",
        ],
    )

    # ——— 7 ———
    h1("7) خارج نطاق v1 (مؤجّل بقرار)")
    section(
        "7.1 المرحلة 10 — SaaS",
        "منصة اشتراكات متعددة المستأجرين.",
        [
            "Multi-Tenant وAPI Keys ومدفوعات.",
            "مؤجّلة عمداً حتى انتهاء شهر التقييم الحي.",
            "ليست نقصاً في v1 — قرار منتج مستقبلي.",
        ],
    )
    section(
        "7.2 المرحلة 12 — الذكاء المتقدم",
        "تعلّم وتكيّف من تاريخ الصفقات.",
        [
            "Blacklist وRegime وRL.",
            "تحتاج بيانات كافية من التجربة الحية أولاً.",
        ],
    )

    # ——— 8 ———
    h1("8) التشغيل العملي")
    section(
        "8.1 Windows live",
        "استخراج الحزمة وتشغيل البوت مع MT5.",
        [
            "استخرج ZIP إلى C:\\GoldenShield.",
            "افتح XM MT5 وسجّل دخول الحساب (مثال: XMGlobal-MT5 10).",
            "شغّل 00_START.bat واترك النافذة مفتوحة.",
            "Disconnect RDP — لا تعمل Log off أو Shutdown.",
        ],
    )
    section(
        "8.2 Contabo paper",
        "تحليل 24/7 بدون تنفيذ XM.",
        [
            "docker compose على /opt/goldenshield.",
            "EXECUTION_MODE=paper.",
            "لا تفعّل MT5_ENABLED على Linux.",
        ],
    )

    # ——— 9 ———
    h1("9) الخلاصة النهائية")
    for item in [
        "GoldenShield v1 مكتمل 100% لكل ما وصلنا إليه حالياً.",
        "نظام عامل: تحليل هجين + مخاطر + ظل + تنفيذ + تيليجرام + DB.",
        "قواعد واضحة: عرض ≥75 · تلقائي ≥90 · مخاطرة 1%.",
        "بروتوكولات مؤسسية جاهزة اختيارياً (3% Risk / Standard Bonus).",
        "الخطوة التالية: شهر تقييم live ثم قرار SaaS أو ذكاء متقدم.",
    ]:
        bullet(item)
    pdf.ln(2)
    line("— نهاية التقرير التفصيلي — v1 مكتمل 100% —", size=11, bold=True)

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
                    "تقرير GoldenShield التفصيلي — حتى ما وصلنا إليه حالياً\n"
                    "نقاط + شرح كامل لكل بند | v1 مكتمل 100%\n"
                    f"البناء: {BUILD_TAG}"
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
