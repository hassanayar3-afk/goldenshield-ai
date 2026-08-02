"""OBSOLETE — كان يشغّل مجلد Downloads ويسبب نسختين.

استخدم فقط: C:\\GoldenShield_Binance
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.vps_official import obsolete_exit  # noqa: E402


def main() -> int:
    return obsolete_exit("force_start_bot_vps.py")


if __name__ == "__main__":
    raise SystemExit(main())
