"""Remote health probe — UTF-8 Python file (no Arabic inside PowerShell)."""
from __future__ import annotations

from config.settings import get_settings
from data.exchange_client import get_exchange
from execution.binance_position_sync import (
    format_holdings_report,
    sync_binance_spot_positions,
)
from execution.trade_executor import TradeExecutor
from operations.dashboard_templates import format_main_dashboard, format_market_overview
from operations.telegram_bot import TelegramBot
from operations.telegram_keyboards import main_menu_keyboard, positions_list_keyboard


def main() -> None:
    s = get_settings()
    print("demo", s.binance_demo_trading, "mode", s.execution_mode, "backend", s.execution_backend)
    print("manual", s.manual_entry_required, "auto_min", s.auto_entry_min_percent)

    ex = get_exchange()
    bal = ex.fetch_balance() or {}
    usdt = bal.get("USDT") or {}
    free = float(usdt.get("free") if isinstance(usdt, dict) else (usdt or 0))
    print(f"USDT_FREE={free:.4f}")

    executor = TradeExecutor()
    restored = executor.restore_open_positions()
    synced = sync_binance_spot_positions(executor)
    print("restored", restored, "synced", synced)
    print("open_count", executor.position_manager.count())
    positions = executor.position_manager.all()
    for p in positions:
        print(f"POS {p.symbol} {p.side.value} amt={p.amount:.8g} entry={p.entry_price:.6g}")

    tg = TelegramBot()
    # Clean Arabic dashboard (not a PowerShell-embedded string)
    menu = format_main_dashboard(
        env=str(getattr(s, "environment", "demo") or "demo"),
        mode=str(s.execution_mode or "PAPER"),
        balance=free,
        daily_pnl="—",
        open_count=len(positions),
        paused=False,
        kill_switch="OK",
        pairs_count=len(s.trading_pairs or []),
        floating_pnl=None,
    )
    mid = tg.send_message(menu, reply_markup=main_menu_keyboard(paused=False))
    print("MAIN_MENU_MSG", mid)
    print("MENU_AR_OK", "لوحة" in menu or "الحالة" in menu)

    report = format_holdings_report(executor)
    prices = {p.symbol: p.entry_price for p in positions}
    pmid = tg.send_message(
        report, reply_markup=positions_list_keyboard(positions, prices, live=False)
    )
    print("POSITIONS_MSG", pmid)

    entries = [
        {"symbol": sym, "score": 5, "signal": "WAIT", "price": 1.0}
        for sym in (s.trading_pairs or [])[:5]
    ]
    market_text = format_market_overview(entries)
    print("MARKET_VIEW_OK", "GoldenShield" in market_text and ("السوق" in market_text or "مراقبة" in market_text or "WAIT" in market_text))
    print("HEALTH_OK")


if __name__ == "__main__":
    main()
