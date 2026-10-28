#!/usr/bin/env python3
"""Fix common .env / saqr.env issues (ZWSP, leading + on Telegram token, missing SAQR keys)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

INVISIBLE = re.compile(r"[\u200b-\u200d\ufeff\u2060\u00ad]+")

DEFAULTS: dict[str, str] = {
    "SAQR_REQUIRE_INTEGRATED_DEMO": "false",
    "SAQR_ENABLE_TRADING": "false",
    "SAQR_ENABLE_LIVE_ACK": "false",
    "SAQR_WAL_PATH": "data/saqr.wal.jsonl",
    "SAQR_WS_RECONNECT_SECS": "3",
    "SAQR_INTEGRATION_INTERVAL_SECS": "300",
}


def clean_value(key: str, val: str) -> str:
    v = INVISIBLE.sub("", val.strip().strip('"').strip("'"))
    if key == "TELEGRAM_BOT_TOKEN" and v.startswith("+"):
        v = v.lstrip("+")
    return v


def process(text: str) -> str:
    lines = text.splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            out.append(line)
            continue
        if "=" not in line:
            out.append(line)
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        val = clean_value(key, rest)
        seen.add(key.upper())
        out.append(f"{key}={val}")
    insert_at = 0
    for i, line in enumerate(out):
        if line.startswith("SAQR_MODE="):
            insert_at = i + 1
            break
    to_add = []
    for k, v in DEFAULTS.items():
        if k not in seen:
            to_add.append(f"{k}={v}")
    if to_add:
        out[insert_at:insert_at] = to_add
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/saqr.env")
    if not path.is_file():
        print(f"Missing: {path}", file=sys.stderr)
        return 1
    raw = path.read_text(encoding="utf-8", errors="replace")
    fixed = process(raw)
    path.write_text(fixed, encoding="utf-8", newline="\n")
    print(f"Sanitized: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
