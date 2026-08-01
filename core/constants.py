# الأطر الزمنية المعتمدة في النظام
TIMEFRAMES: tuple[str, ...] = ("15m", "1h", "4h")

TIMEFRAME_LABELS: dict[str, str] = {
    "15m": "M15",
    "1h": "H1",
    "4h": "H4",
}

# عتبات الجودة
SIGNAL_MIN_SCORE: float = 8.0
SIGNAL_MAX_SCORE: int = 10
SIGNAL_MIN_PERCENT: int = 75
SIGNAL_NOTIFY_MIN_PERCENT: int = 85  # إرسال تيليجرام من 85 فما فوق
SIGNAL_MAX_PERCENT: int = 100

# دخول تلقائي من 90/100 فما فوق (درجة 9–10)
# 75–89: يدوي فقط | 90–99: تلقائي ناعم | 100: تلقائي قوي / ذهبي
SIGNAL_AUTO_SOFT_MIN: int = 90
SIGNAL_AUTO_SOFT_MAX_EXCLUSIVE: int = 100
SIGNAL_AUTO_STRONG_MIN: int = 100
SOFT_AUTO_MAX_POSITIONS: int = 5
STRONG_AUTO_MAX_POSITIONS: int = 12
SIGNAL_AUTO_PERCENT: int = 90
GOLDEN_OPPORTUNITY_PERCENT: int = 100

# 8=75 (يدوي) | 9=90 (تلقائي ناعم) | 10=100 (تلقائي ذهبي)
SCORE_PERCENT_MAP: dict[int, int] = {
    0: 0,
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50,
    6: 60,
    7: 70,
    8: 75,
    9: 90,
    10: 100,
}


def score_to_percent(score: int | float) -> int:
    key = int(round(float(score)))
    return SCORE_PERCENT_MAP.get(key, 0)


def meets_signal_minimum(score: int | float) -> bool:
    return score_to_percent(score) >= SIGNAL_MIN_PERCENT


def meets_telegram_notify_minimum(
    score: int | float,
    min_percent: int | None = None,
) -> bool:
    """عتبة إرسال الإشارات إلى تيليجرام (افتراضي 85/100)."""
    threshold = SIGNAL_NOTIFY_MIN_PERCENT if min_percent is None else int(min_percent)
    return score_to_percent(score) >= threshold


def is_golden_opportunity(score: int | float) -> bool:
    """فرصة ذهبية = 100/100 (درجة 10)."""
    return score_to_percent(score) >= GOLDEN_OPPORTUNITY_PERCENT


def meets_auto_entry_minimum(score: int | float, auto_percent: int | None = None) -> bool:
    threshold = SIGNAL_AUTO_PERCENT if auto_percent is None else int(auto_percent)
    return score_to_percent(score) >= threshold


def is_auto_entry_allowed(
    score: int | float,
    open_positions: int,
    *,
    soft_min: int = SIGNAL_AUTO_SOFT_MIN,
    soft_max_exclusive: int = SIGNAL_AUTO_SOFT_MAX_EXCLUSIVE,
    strong_min: int = SIGNAL_AUTO_STRONG_MIN,
    soft_max_positions: int = SOFT_AUTO_MAX_POSITIONS,
    strong_max_positions: int = STRONG_AUTO_MAX_POSITIONS,
) -> tuple[bool, str]:
    """تلقائي من 90/100 فما فوق — أقل من ذلك يدوي فقط."""
    pct = score_to_percent(score)
    if pct >= strong_min:
        if open_positions >= strong_max_positions:
            return (
                False,
                f"{pct}/100 — امتلأ الحد {strong_max_positions} صفقة",
            )
        label = "فرصة ذهبية ⚡" if is_golden_opportunity(score) else "تلقائي قوي"
        return (
            True,
            f"{label} {pct}/100 — دخول تلقائي — مراكز {open_positions + 1}/{strong_max_positions}",
        )
    if soft_min <= pct < soft_max_exclusive:
        if open_positions >= soft_max_positions:
            return (
                False,
                f"{pct}/100 — الشريحة الناعمة ممتلئة ({soft_max_positions} صفقات) — يدوي أو انتظر إغلاق",
            )
        return (
            True,
            f"تلقائي ⚡ {pct}/100 — مراكز {open_positions + 1}/{soft_max_positions}",
        )
    if meets_signal_minimum(score):
        return (
            False,
            f"{pct}/100 — يدوي فقط (غير مضمون — التلقائي من {soft_min}/100 فما فوق)",
        )
    return False, f"{pct}/100 دون 75 — لا دخول تلقائي"


def required_auto_percent_for_slots(
    open_positions: int,
    *,
    base_percent: int | None = None,
    soft_max_positions: int = SOFT_AUTO_MAX_POSITIONS,
    soft_min: int = SIGNAL_AUTO_SOFT_MIN,
    strong_min: int = SIGNAL_AUTO_STRONG_MIN,
) -> int:
    if open_positions >= soft_max_positions:
        return strong_min
    return soft_min if base_percent is None else int(base_percent)

# مؤشرات أساسية
SMA_PERIOD: int = 20
DEFAULT_OHLCV_LIMIT: int = 20

# اتصال
HEARTBEAT_TIMEOUT_SECONDS: int = 180

# فلاتر التنفيذ
MAX_SPREAD_PCT: float = 0.15
RSI_PERIOD: int = 14
ATR_PERIOD: int = 14
OHLCV_ANALYSIS_LIMIT: int = 50

# الذكاء الهجين — مرجع فقط
NEWS_BLACKOUT_MINUTES: int = 5
VIX_THRESHOLD: float = 30.0
BONDS_YIELD_SPIKE_PCT: float = 3.0
FEAR_GREED_EXTREME_LOW: int = 20
FEAR_GREED_EXTREME_HIGH: int = 80
WHALE_WALL_MULTIPLIER: float = 3.0
SENTIMENT_ANOMALY_THRESHOLD: float = 2.0

# التنفيذ — قيم افتراضية (R:R مؤسسي 1:3)
DEFAULT_SL_PCT: float = 0.03
DEFAULT_RR_RATIO: float = 3.0
