"""OBSOLETE — منطق تعطيل Downloads القديم؛ التشغيل الرسمي فقط من Binance.

استخدم: scripts/force_single_clean_bot2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.vps_official import obsolete_exit  # noqa: E402


def main() -> int:
    return obsolete_exit("stabilize_bot_autostart.py")


if __name__ == "__main__":
    raise SystemExit(main())
