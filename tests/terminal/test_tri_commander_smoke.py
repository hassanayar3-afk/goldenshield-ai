"""Tri-Commander smoke — يُشغَّل مع scripts/smoke_tri_commander.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_tri_commander_smoke_script():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "smoke_tri_commander.py")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "TRI_SMOKE_OK" in proc.stdout
