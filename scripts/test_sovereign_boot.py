#!/usr/bin/env python3
"""Smoke test sovereign layout imports (no network)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from gateway_api.fast_router import app
from risk_sentinel.spread_guard import max_spread_bps
from data_highway.memory_buffers import ring_maxlen

assert app.title
assert max_spread_bps() > 0
assert ring_maxlen() == 500 or ring_maxlen() > 0
print("sovereign boot OK")
