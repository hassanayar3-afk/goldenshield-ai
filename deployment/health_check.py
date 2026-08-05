#!/usr/bin/env python3
"""فحص صحة GoldenShield — يُستخدم من Docker healthcheck."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))


def main() -> int:
    try:
        from config.settings import load_settings

        settings = load_settings(reload=True)
    except Exception as exc:
        print("SETTINGS_FAIL", exc)
        return 1

    db_parent = Path(settings.db_path).parent
    if not db_parent.exists():
        print("DB_DIR_MISSING", db_parent)
        return 1

    logs_dir = BASE / "storage" / "logs"
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True, exist_ok=True)

    # Binance ping — مصدر البيانات (paper و live)
    try:
        with urlopen("https://api.binance.com/api/v3/ping", timeout=10) as resp:
            if getattr(resp, "status", 200) != 200:
                print("BINANCE_PING_FAIL")
                return 1
    except Exception as exc:
        print("BINANCE_PING_ERROR", exc)
        return 1

    backend = (os.getenv("EXECUTION_BACKEND") or settings.execution_backend or "binance").lower()
    mode = (os.getenv("EXECUTION_MODE") or settings.execution_mode or "paper").lower()
    print(f"OK mode={mode} backend={backend} env={settings.env}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
