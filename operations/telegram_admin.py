"""أوامر الإدارة — إضافة عملات (Binance فقط؛ MT5 معطّل)."""

from __future__ import annotations

from config.settings import get_settings
from operations.symbol_registry import get_symbol_registry


def _mt5_disabled_msg(feature: str) -> str:
    return (
        f"⛔ <b>{feature}</b> غير متاح — المشروع يعمل على <b>Binance فقط</b>.\n"
        "MetaTrader ملغى من التشغيل الحالي."
    )


def handle_admin_command(text: str) -> str | None:
    parts = text.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower()
    registry = get_symbol_registry()
    settings = get_settings()
    mt5_on = bool(getattr(settings, "mt5_enabled", False))

    if cmd in {"/add", "/add_crypto"} and len(parts) >= 2:
        pair = parts[1]
        registry.add_crypto(pair, enabled=True)
        return f"✅ أُضيفت العملة <b>{pair}</b> للمراقبة والتداول."

    if cmd == "/add_stock":
        if not mt5_on:
            return _mt5_disabled_msg("إضافة الأسهم")
        if len(parts) < 2:
            return "استخدم: /add_stock AAPL"
        ticker = parts[1]
        registry.add_stock(ticker, enabled=True)
        return f"✅ أُضيف السهم <b>STOCK/{ticker.upper()}</b>."

    if cmd == "/add_forex":
        if not mt5_on:
            return _mt5_disabled_msg("إضافة الفوركس")
        if len(parts) < 2:
            return "استخدم: /add_forex EURUSD"
        pair = parts[1]
        registry.add_forex(pair, enabled=True)
        return f"✅ أُضيف الفوركس <b>FOREX/{pair.upper().replace('/', '')}</b>."

    if cmd == "/remove" and len(parts) >= 2:
        symbol_id = parts[1]
        if registry.remove(symbol_id):
            return f"🗑️ أُوقف مراقبة <b>{symbol_id}</b>."
        return f"⚠️ الرمز <b>{symbol_id}</b> غير موجود."

    if cmd in {"/symbols", "/list"}:
        lines = ["<b>الرموز النشطة (Binance):</b>"]
        for spec in registry.all_specs():
            if not spec.enabled:
                continue
            if spec.category != "crypto" and not mt5_on:
                continue
            tag = {"crypto": "🪙", "stock": "📈", "forex": "💱"}.get(spec.category, "•")
            lines.append(f"{tag} {spec.id} <i>({spec.data_source})</i>")
        if len(lines) == 1:
            return "لا رموز نشطة حالياً."
        return "\n".join(lines)

    if cmd == "/sync_mt5":
        if not mt5_on:
            return _mt5_disabled_msg("مزامنة MT5")
        added = registry.sync_from_mt5()
        if not added:
            return "ℹ️ مزامنة MT5: لا رموز جديدة (أو MT5 غير متصل)."
        return "✅ مزامنة MT5 أضافت:\n" + "\n".join(f"• {s}" for s in added)

    if cmd == "/enable_stocks":
        if not mt5_on:
            return _mt5_disabled_msg("تفعيل الأسهم")
        tickers = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META"]
        enabled: list[str] = []
        for ticker in tickers:
            registry.add_stock(ticker, enabled=True)
            enabled.append(f"STOCK/{ticker}")
        return "✅ الأسهم مفعّلة:\n" + "\n".join(f"• {s}" for s in enabled)

    if cmd == "/enable_forex":
        if not mt5_on:
            return _mt5_disabled_msg("تفعيل الفوركس")
        pairs = [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "AUDUSD",
            "USDCAD",
            "USDCHF",
            "NZDUSD",
            "XAUUSD",
            "XAGUSD",
            "USOIL",
        ]
        lines = []
        for pair in pairs:
            registry.add_forex(pair, enabled=True)
            lines.append(f"• FOREX/{pair}")
        return "✅ الفوركس مفعّل:\n" + "\n".join(lines)

    return None
