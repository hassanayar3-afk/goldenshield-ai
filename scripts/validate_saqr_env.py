#!/usr/bin/env python3
"""Preflight: required SAQR .env keys present (never prints secret values)."""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = [
    "SAQR_MODE",
    "SAQR_INITIAL_BALANCE_USD",
    "SAQR_SYMBOL",
    "BINANCE_REST_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SAQR_WEB_BIND_PORT",
]

OPTIONAL_WARN = ["SAQR_TELEGRAM_BRIDGE"]


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".env")
    if not path.is_file():
        print(f"[FAIL] Missing {path}", file=sys.stderr)
        return 1
    env = parse_env(path)
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        print(f"[FAIL] Missing or empty keys: {', '.join(missing)}", file=sys.stderr)
        return 1
    if env.get("SAQR_MODE", "").lower() != "paper":
        print("[WARN] SAQR_MODE is not paper", file=sys.stderr)
    tok = env.get("TELEGRAM_BOT_TOKEN", "")
    if len(tok) < 40 or ":" not in tok:
        print("[FAIL] TELEGRAM_BOT_TOKEN looks truncated or invalid", file=sys.stderr)
        return 1
    if env.get("SAQR_TELEGRAM_BRIDGE", "true").lower() not in ("1", "true", "yes", "on"):
        print("[WARN] SAQR_TELEGRAM_BRIDGE is off — bidirectional bridge disabled", file=sys.stderr)
    print(f"[OK] .env preflight passed ({path.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
