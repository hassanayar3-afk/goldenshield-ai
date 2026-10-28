#!/usr/bin/env python3
"""Rewrite legacy saqr imports to sovereign package layout."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REPLACEMENTS = [
    (r"from utils\.logger_config", "from data_highway.logging_config"),
    (r"from utils\.runtime_env", "from data_highway.runtime_env"),
    (r"from utils\.control_state", "from risk_sentinel.control_state"),
    (r"from utils\.entry_guards", "from risk_sentinel.entry_guards"),
    (r"from utils\.spread_volatility_guard", "from risk_sentinel.spread_guard"),
    (r"from utils\.crash_wrapper", "from risk_sentinel.crash_watchdog"),
    (r"from utils\.pnl", "from risk_sentinel.pnl"),
    (r"from database\.db_manager", "from data_highway.sqlite_store"),
    (r"from gateway\.binance_client", "from gateway_api.binance_client"),
    (r"from gateway\.stream_service", "from gateway_api.stream_service"),
    (r"from gateway\.sync_service", "from gateway_api.sync_service"),
    (r"from gateway\.control_service", "from gateway_api.control_service"),
    (r"from gateway\.connection_manager", "from gateway_api.connection_manager"),
    (r"from gateway\.recovery_service", "from gateway_api.recovery_service"),
    (r"from gateway\.user_stream", "from gateway_api.user_stream"),
    (r"from gateway\.demo_seed", "from gateway_api.demo_seed"),
    (r"from gateway\.global_circuit_breaker", "from risk_sentinel.circuit_breaker"),
    (r"from gateway\.global_circuit_breaker import GlobalCircuitBreaker", "from risk_sentinel.circuit_breaker import GlobalCircuitBreaker"),
    (r"from utils\.spread_volatility_guard import", "from risk_sentinel.spread_guard import"),
    (r"setup_logger\(\"saqr\.", "setup_logger(\"saqr."),
]

DIRS = ["core_engine", "risk_sentinel", "data_highway", "gateway_api"]


def main() -> None:
    for d in DIRS:
        for path in (ROOT / d).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            orig = text
            for pat, repl in REPLACEMENTS:
                text = re.sub(pat, repl, text)
            if text != orig:
                path.write_text(text, encoding="utf-8")
    print("imports fixed")


if __name__ == "__main__":
    main()
