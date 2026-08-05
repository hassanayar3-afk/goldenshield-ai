"""أوامر الإدارة — إضافة عملات Binance فقط."""

from __future__ import annotations

from operations.symbol_registry import get_symbol_registry


def _binance_only(feature: str) -> str:
    return (
        f"⛔ <b>{feature}</b> غير متاح.\n"
        "GoldenShield يعمل على <b>Binance</b> فقط — لا فوركس ولا أسهم ولا أي منصة أخرى."
    )


def handle_admin_command(text: str) -> str | None:
    parts = text.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower()
    registry = get_symbol_registry()

    if cmd in {"/add", "/add_crypto"} and len(parts) >= 2:
        pair = parts[1]
        if registry.add_crypto(pair, enabled=True):
            return f"✅ أُضيفت العملة <b>{pair}</b> للمراقبة والتداول على Binance."
        return (
            f"⛔ تعذر إضافة <b>{pair}</b> — يُقبل فقط أزواج Binance "
            "(مثل BTC/USDT)."
        )

    if cmd in {
        "/add_stock",
        "/add_forex",
        "/enable_stocks",
        "/enable_forex",
        "/sync_mt5",
    }:
        return _binance_only(cmd)

    if cmd == "/remove" and len(parts) >= 2:
        symbol_id = parts[1]
        if registry.remove(symbol_id):
            return f"🗑️ أُوقف مراقبة <b>{symbol_id}</b>."
        return f"⚠️ الرمز <b>{symbol_id}</b> غير موجود."

    if cmd in {"/symbols", "/list"}:
        lines = ["<b>الرموز النشطة (Binance فقط):</b>"]
        for spec in registry.all_specs():
            if not spec.enabled:
                continue
            lines.append(f"🪙 {spec.id}")
        if len(lines) == 1:
            return "لا رموز نشطة حالياً."
        return "\n".join(lines)

    return None
