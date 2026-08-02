"""OBSOLETE — كان يفضّل Downloads / C:\\GoldenShield.

استخدم: scripts/force_single_clean_bot2.py أو C:\\GoldenShield_Binance\\00_START.bat
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.vps_official import obsolete_exit  # noqa: E402


def main() -> int:
    return obsolete_exit("start_bot_vps_now.py")


if __name__ == "__main__":
    raise SystemExit(main())
