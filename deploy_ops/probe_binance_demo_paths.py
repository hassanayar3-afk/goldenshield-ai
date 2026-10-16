#!/usr/bin/env python3
"""Try alternate Demo API / cache paths — prints OK/FAIL per path (no secrets)."""

from __future__ import annotations

import sys
from pathlib import Path


def _root() -> Path:
    raw = __import__("os").getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance"
    p = Path(raw.strip())
    return p if p.is_dir() else Path(__file__).resolve().parents[1]


def main() -> int:
    root = _root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from data.binance_resilient import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
