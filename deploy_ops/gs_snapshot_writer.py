"""Sidecar: refresh binance_snapshot.json for Mobile API (try-except, never crash)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", Path(__file__).resolve().parents[1]))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INTERVAL = float(os.getenv("SNAPSHOT_WRITER_INTERVAL_SEC", "25") or 25)


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    while True:
        try:
            from terminal_app.services import binance_mirror as bm

            bm.binance_snapshot(force=True)
        except Exception:
            pass
        time.sleep(max(10.0, INTERVAL))


if __name__ == "__main__":
    main()
