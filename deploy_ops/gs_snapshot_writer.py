#!/usr/bin/env python3
"""Sidecar: refresh binance_snapshot.json on an interval (independent of Mobile API / browser)."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", r"C:\GoldenShield_Binance")).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG = logging.getLogger("gs_snapshot_writer")


def _configure_logging() -> None:
    try:
        log_dir = ROOT / "storage" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "gs_snapshot_writer.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        LOG.addHandler(fh)
    except Exception:
        pass
    LOG.setLevel(logging.INFO)


def _interval_sec() -> float:
    try:
        raw = os.getenv("GS_SNAPSHOT_WRITER_SEC", "30").strip() or "30"
        return max(15.0, float(raw))
    except Exception:
        return 30.0


def main() -> int:
    _configure_logging()
    LOG.info("SNAPSHOT_WRITER_START root=%s interval=%s", ROOT, _interval_sec())
    while True:
        try:
            from terminal_app.services import binance_mirror as bm

            snap = bm.resolve_display_snapshot(force=True)
            eq = snap.get("equity")
            LOG.info(
                "SNAPSHOT_TICK ok=%s equity=%s source=%s",
                snap.get("ok"),
                eq,
                snap.get("source"),
            )
        except Exception as exc:
            LOG.exception("SNAPSHOT_TICK_FAIL %s", exc)
        time.sleep(_interval_sec())


if __name__ == "__main__":
    raise SystemExit(main())
