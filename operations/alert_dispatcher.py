"""توزيع التنبيهات — Discord + سجلات (Telegram removed)."""

from __future__ import annotations

from enum import Enum

from config.settings import get_settings
from operations.error_logger import log_error, log_operation
from operations.message_templates import (
    format_alert_message,
    format_emergency_message,
    format_opened_trades_digest,
    format_trade_close_message,
    format_trade_open_message,
)
from operations.shutdown_guard import should_block_signals


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    EMERGENCY = "emergency"


def _strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text or "").strip()


def _discord_send(text: str) -> bool:
    try:
        from bridges.discord.discord_notify import send_discord

        plain = _strip_html(text)
        return bool(send_discord(plain[:1900]))
    except Exception:
        return False


class AlertDispatcher:
    def __init__(self) -> None:
        pass

    def _signals_only(self) -> bool:
        raw = (get_settings().discord_signals_only if hasattr(get_settings(), "discord_signals_only") else False)
        return bool(raw)

    def _log_plain(self, level: AlertLevel, title: str, detail: str = "") -> None:
        text = f"[{level.value.upper()}] {title}"
        if detail:
            text += f"\n{detail}"
        log_operation(text)
        if level in {AlertLevel.WARNING, AlertLevel.EMERGENCY}:
            log_error(f"{title}: {detail}" if detail else title)

    def _blocked(self) -> bool:
        return should_block_signals()

    def dispatch(self, level: AlertLevel, title: str, detail: str = "") -> bool:
        self._log_plain(level, title, detail)
        if self._blocked():
            return False
        if self._signals_only() and level != AlertLevel.EMERGENCY:
            return False
        return _discord_send(format_alert_message(level.value, title, detail))

    def send_formatted(self, text: str, *, plain_log: str) -> bool:
        log_operation(plain_log)
        if self._blocked():
            return False
        if self._signals_only():
            return False
        return _discord_send(text)

    def emergency(self, title: str, detail: str = "") -> bool:
        self._log_plain(AlertLevel.EMERGENCY, title, detail)
        return _discord_send(format_emergency_message(title, detail))

    def trade_opened(self, symbol: str, detail: str) -> bool:
        plain = f"[INFO] صفقة جديدة {symbol}\n{detail}"
        log_operation(plain)
        if self._blocked():
            return False
        return _discord_send(format_trade_open_message(symbol, detail))

    def trades_opened_batch(self, opened: list[dict]) -> bool:
        if not opened:
            return False
        plain_lines = [f"{item.get('symbol')}: {item.get('detail', '')}" for item in opened]
        log_operation("[INFO] صفقات فُتحت\n" + "\n".join(plain_lines))
        if self._blocked():
            return False
        return _discord_send(format_opened_trades_digest(opened))

    def trade_closed(self, symbol: str, pnl: float, reason: str) -> bool:
        sign = "+" if pnl >= 0 else ""
        plain = f"[INFO] إغلاق {symbol}\nPnL: {sign}{pnl:.2f} USDT | {reason}"
        log_operation(plain)
        if self._blocked():
            return False
        return _discord_send(format_trade_close_message(symbol, pnl, reason))

    def kill_switch_activated(self, reason: str) -> bool:
        return self.emergency("Kill Switch", reason)
