"""أزرار لوحة التحكم — حسب دستور GoldenShield (بسيطة ومختصرة)."""

from __future__ import annotations

from config.settings import get_settings


def _encode_symbol(symbol: str) -> str:
    return symbol.replace("/", "")


def decode_symbol(token: str) -> str:
    from operations.symbol_registry import get_symbol_registry

    for pair in get_symbol_registry().active_pairs():
        if _encode_symbol(pair) == token:
            return pair
    if token.startswith("STOCK") and len(token) > 5:
        return f"STOCK/{token[5:]}"
    if token.startswith("FOREX") and len(token) > 5:
        return f"FOREX/{token[5:]}"
    if len(token) > 4 and token.endswith("USDT"):
        return f"{token[:-4]}/USDT"
    return token


def encode_symbol(symbol: str) -> str:
    return _encode_symbol(symbol)


def main_menu_keyboard(*, paused: bool) -> dict:
    toggle = (
        {"text": "▶️ تشغيل", "callback_data": "act:resume"}
        if paused
        else {"text": "⏸️ إيقاف", "callback_data": "act:pause"}
    )
    return {
        "inline_keyboard": [
            [
                {"text": "📡 الإشارات", "callback_data": "view:market"},
                {"text": "📂 مراكزي", "callback_data": "view:positions"},
            ],
            [
                {"text": "📜 سجل الصفقات", "callback_data": "view:history"},
                {"text": "📋 التقرير", "callback_data": "view:report"},
            ],
            [
                toggle,
            ],
            [{"text": "❌ إغلاق الصفقات", "callback_data": "view:close_menu"}],
            [
                {"text": "🛠 صحة المؤسسة", "callback_data": "view:enterprise_health"},
                {"text": "🔁 تشخيص", "callback_data": "act:enterprise_diag"},
            ],
            [{"text": "🚨 طوارئ — إيقاف كامل", "callback_data": "act:panic"}],
        ]
    }


def close_menu_keyboard() -> dict:
    """قائمة إغلاق ثلاثية — بدون حذف زر الإغلاق من الرئيسية."""
    return {
        "inline_keyboard": [
            [{"text": "🟢 إغلاق الرابحة فقط", "callback_data": "act:close_winners"}],
            [{"text": "🔴 إغلاق الخاسرة فقط", "callback_data": "act:close_losers"}],
            [{"text": "❌ إغلاق جميع الصفقات", "callback_data": "act:close_all"}],
            [{"text": "◀️ الرئيسية", "callback_data": "view:main"}],
        ]
    }


def report_period_keyboard() -> dict:
    """فترات التقرير — مع الحفاظ على التقرير اليومي والسجل."""
    return {
        "inline_keyboard": [
            [
                {"text": "📅 اليوم", "callback_data": "view:report"},
                {"text": "🗓 أسبوع", "callback_data": "view:report_week"},
            ],
            [
                {"text": "📆 شهر", "callback_data": "view:report_month"},
                {"text": "📜 السجل", "callback_data": "view:history"},
            ],
            [{"text": "◀️ الرئيسية", "callback_data": "view:main"}],
        ]
    }


def market_keyboard(symbols: list[str], *, entries: list[dict] | None = None) -> dict:
    """أزرار الأزواج مرتبة من الأضعف للأقوى مع أيقونة القوة."""
    from core.constants import SIGNAL_NOTIFY_MIN_PERCENT, score_to_percent

    score_map = {e["symbol"]: int(e.get("score", 0)) for e in (entries or [])}
    signal_map = {e["symbol"]: str(e.get("signal", "WAIT")) for e in (entries or [])}
    ordered = sorted(symbols, key=lambda s: score_map.get(s, 0))
    rows: list[list[dict]] = []
    row: list[dict] = []
    for symbol in ordered:
        score = score_map.get(symbol, 0)
        percent = score_to_percent(score)
        signal = signal_map.get(symbol, "WAIT")
        # أخضر فقط إذا BUY/SELL ضمن عتبة إرسال تيليجرام (≥70 هجين)
        if signal in {"BUY SIGNAL", "SELL SIGNAL"} and percent >= SIGNAL_NOTIFY_MIN_PERCENT:
            icon = "🟢"
        elif percent >= SIGNAL_NOTIFY_MIN_PERCENT:
            icon = "🔵"
        elif percent >= 70:
            icon = "🟡"
        elif percent >= 50:
            icon = "🟠"
        else:
            icon = "🔴"
        row.append(
            {
                "text": f"{icon} {symbol.split('/')[0]} {percent}",
                "callback_data": f"sym:{encode_symbol(symbol)}",
            }
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "◀️ الرئيسية", "callback_data": "view:main"}])
    return {"inline_keyboard": rows}


def trade_entry_keyboard(symbol: str, *, can_enter: bool) -> dict:
    token = encode_symbol(symbol)
    rows: list[list[dict]] = []
    if can_enter:
        rows.append([{"text": "✅ دخول الصفقة الآن", "callback_data": f"enter:{token}"}])
    else:
        rows.append(
            [{"text": "⏳ غير جاهزة — حدّث بعد دورة", "callback_data": f"sym:{token}"}]
        )
    rows.append(
        [
            {"text": "🔄 تحديث", "callback_data": f"sym:{token}"},
            {"text": "◀️ الإشارات", "callback_data": "view:market"},
        ]
    )
    return {"inline_keyboard": rows}


def position_trade_keyboard(symbol: str) -> dict:
    token = encode_symbol(symbol)
    return {
        "inline_keyboard": [
            [
                {"text": "❌ إغلاق الصفقة", "callback_data": f"close:{token}"},
                {"text": "🔄 تحديث", "callback_data": f"pos:{token}"},
            ],
            [
                {"text": "◀️ مراكزي", "callback_data": "view:positions"},
                {"text": "🏠 الرئيسية", "callback_data": "view:main"},
            ],
        ]
    }


def positions_list_keyboard(
    positions: list,
    prices: dict[str, float],
    *,
    live: bool = False,
    live_scores: dict[str, int] | None = None,
) -> dict:
    """أزرار الصفقات: القوة + نسبة الربح/الخسارة."""
    from core.constants import score_to_percent
    from operations.dashboard_templates import compute_open_floating_pnl

    live_scores = live_scores or {}
    rows: list[list[dict]] = []
    row: list[dict] = []
    for pos in positions:
        current = float(prices.get(pos.symbol, pos.entry_price))
        if pos.side.value == "buy":
            pnl_pct = (
                ((current - pos.entry_price) / pos.entry_price) * 100
                if pos.entry_price > 0
                else 0.0
            )
        else:
            pnl_pct = (
                ((pos.entry_price - current) / pos.entry_price) * 100
                if pos.entry_price > 0
                else 0.0
            )
        icon = "🟢" if pnl_pct >= 0 else "🔴"
        entry_score = int(getattr(pos, "signal_score", 0) or 0)
        live_sc = int(live_scores.get(pos.symbol, 0) or 0)
        strength = (
            score_to_percent(entry_score)
            if entry_score > 0
            else (score_to_percent(live_sc) if live_sc > 0 else 0)
        )
        strength_txt = str(strength) if strength > 0 else "—"
        name = pos.symbol.split("/")[0]
        pnl_sign = "+" if pnl_pct >= 0 else ""
        text = f"{icon} {name} | {pnl_sign}{pnl_pct:.1f}% | ق{strength_txt}"
        if len(text.encode("utf-8")) > 64:
            text = f"{icon} {name} {pnl_sign}{pnl_pct:.1f}%"
        row.append(
            {
                "text": text,
                "callback_data": f"pos:{encode_symbol(pos.symbol)}",
            }
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if live:
        try:
            total_pnl, _ = compute_open_floating_pnl(positions, prices)
            tsign = "+" if total_pnl >= 0 else ""
            live_label = f"مجموع {tsign}{total_pnl:,.2f}$"
        except Exception:
            live_label = "🔴 بث حي يعمل"
        rows.append(
            [
                {"text": live_label, "callback_data": "view:positions"},
                {"text": "🔄 تحديث الآن", "callback_data": "view:positions"},
            ]
        )
    else:
        rows.append([{"text": "🔄 تحديث", "callback_data": "view:positions"}])
    rows.append(
        [
            {"text": "📜 سجل المغلقة", "callback_data": "view:history"},
            {"text": "◀️ الرئيسية", "callback_data": "view:main"},
        ]
    )
    return {"inline_keyboard": rows}


def history_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 تحديث السجل", "callback_data": "view:history"},
                {"text": "📂 مراكزي", "callback_data": "view:positions"},
            ],
            [
                {"text": "📋 تقرير أسبوع", "callback_data": "view:report_week"},
                {"text": "📋 تقرير شهر", "callback_data": "view:report_month"},
            ],
            [{"text": "◀️ الرئيسية", "callback_data": "view:main"}],
        ]
    }


def back_to_main_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📜 سجل الصفقات", "callback_data": "view:history"},
                {"text": "◀️ الرئيسية", "callback_data": "view:main"},
            ]
        ]
    }
