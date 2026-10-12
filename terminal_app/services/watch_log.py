"""مراقبة سجل البوت — تنبيهات Mobile."""

from __future__ import annotations

import threading
import time

from terminal_app.config import ROOT
from terminal_app.services import mobile_core as core


def watch_bot_log_for_alerts() -> None:
    log = ROOT / "storage" / "logs" / "bot_stdout.log"
    last_size = log.stat().st_size if log.exists() else 0
    try:
        for row in core._parse_signals_from_log():
            core._last_score_bucket[row["sym"]] = core._score_bucket(int(row["score"]))
    except Exception:
        pass
    while True:
        try:
            time.sleep(3)
            if not log.exists():
                continue
            size = log.stat().st_size
            if size < last_size:
                last_size = 0
            if size == last_size:
                core._parse_signals_from_log()
                continue
            with log.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(last_size)
                chunk = handle.read()
                last_size = handle.tell()
            for line in chunk.splitlines():
                low = line.lower()
                row = core._parse_signal_line(line)
                if row:
                    core._maybe_alert_signal(row)
                    continue
                if "دخول تلقائي" in line or ("auto" in low and "entry" in low):
                    core._push_alert("auto_entry", "⚡ دخول تلقائي", line[:180], level="trade")
                elif "هدف" in line and ("1/3" in line or "2/3" in line or "3/3" in line):
                    core._push_alert("target", "🎯 هدف متدرج", line[:180], level="trade")
                elif "kill switch" in low:
                    core._push_alert("kill", "🚨 Kill Switch", line[:180], level="emergency")
            core._parse_signals_from_log()
        except Exception:
            time.sleep(5)


def start_watch_log_thread() -> threading.Thread:
    thread = threading.Thread(target=watch_bot_log_for_alerts, daemon=True, name="gs-watch-log")
    thread.start()
    return thread
