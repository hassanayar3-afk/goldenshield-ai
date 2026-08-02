"""Official Windows bot root only — no Downloads, no C:\\GoldenShield."""

from __future__ import annotations

import os
from pathlib import Path

OFFICIAL_ROOT = Path(
    os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", r"C:\GoldenShield_Binance")
)
OFFICIAL_ROOT_STR = str(OFFICIAL_ROOT)

FORBIDDEN_ROOTS = (
    r"C:\GoldenShield",
    r"C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227",
    r"C:\Users\Administrator\Downloads\Telegram Desktop\GOLDENSHIELD_BINANCE_DEMO",
)


def assert_official_only(label: str = "script") -> str:
    """Return official root; log ignored legacy paths."""
    print(f"[{label}] OFFICIAL_ROOT={OFFICIAL_ROOT_STR}")
    for bad in FORBIDDEN_ROOTS:
        if bad.lower() == OFFICIAL_ROOT_STR.lower():
            continue
        print(f"[{label}] ignored legacy path: {bad}")
    return OFFICIAL_ROOT_STR


def obsolete_exit(script_name: str, use_instead: str = r"C:\GoldenShield_Binance") -> int:
    print(
        f"OBSOLETE: {script_name} was retired.\n"
        f"It used Downloads / C:\\GoldenShield and caused duplicate bots.\n"
        f"Use only: {use_instead}\\00_START.bat  or scripts that target that folder."
    )
    return 1
