# -*- coding: utf-8 -*-
"""نبض حي للـ CMD و bot_stdout.log — طبقة مضافة فوق لوحة الإشارات."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def no_sleep_mode_enabled() -> bool:
    raw = (os.getenv("NO_SLEEP_MODE", "true") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def effective_loop_seconds(raw: int | float | None = None) -> int:
    """فاصل الدورة الفعلي — في وضع No Sleep: 3–5 ثوانٍ."""
    try:
        value = int(raw if raw is not None else os.getenv("LOOP_INTERVAL_SECONDS", "4") or 4)
    except (TypeError, ValueError):
        value = 4
    if no_sleep_mode_enabled():
        return max(3, min(5, value))
    return max(1, value)


def effective_live_signals_seconds() -> int:
    try:
        raw = int(os.getenv("TELEGRAM_LIVE_SIGNALS_SECONDS", "4") or 4)
    except (TypeError, ValueError):
        raw = 4
    if no_sleep_mode_enabled():
        return max(3, min(5, raw))
    return max(1, raw)


def print_cycle_pulse_header(loop_seconds: int) -> None:
    try:
        print(
            f"--- ⚡ نبض فحص السوق | دورة جديدة | فاصل ~{loop_seconds}s | No-Sleep=ON ---",
            flush=True,
        )
    except Exception:
        pass


def print_console_signals_board(
    all_entries: list[dict],
    *,
    interval_seconds: float | int = 4,
) -> None:
    """طباعة لوحة الإشارات في CMD/السجل لحظياً."""
    try:
        from operations.dashboard_templates import format_console_signals_board

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
        board = format_console_signals_board(
            all_entries,
            interval_seconds=float(interval_seconds or 4),
            updated_at=ts,
        )
        print(board, flush=True)
        try:
            sys.stdout.flush()
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("print_console_signals_board: %s", exc)


def print_cycle_pulse_footer(loop_seconds: int, *, open_count: int = 0) -> None:
    try:
        extra = f" | مراكز مفتوحة: {open_count}" if open_count else ""
        print(
            f"--- ✅ نبض اكتمل — التالي خلال ~{loop_seconds}s{extra} ---",
            flush=True,
        )
    except Exception:
        pass
