#!/usr/bin/env python3
"""Smoke tests for spread guard, circuit breaker env parsing, logging rotation config."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from utils.spread_volatility_guard import _range_bps, max_spread_bps, max_volatility_bps
from gateway.global_circuit_breaker import _loss_trip_fraction
from utils.logger_config import get_log_ring, setup_logger


def test_range_bps() -> None:
    flat = _range_bps([100.0] * 10)
    assert flat == 0.0
    volatile = _range_bps([100.0] * 4 + [100.0, 105.0, 95.0, 102.0] * 5)
    assert volatile > 0.0


def test_loss_trip_fraction() -> None:
    os.environ["GLOBAL_CIRCUIT_LOSS_PCT"] = "7"
    assert abs(_loss_trip_fraction() - 0.07) < 1e-9
    os.environ["GLOBAL_CIRCUIT_LOSS_PCT"] = "0.08"
    assert abs(_loss_trip_fraction() - 0.08) < 1e-9


def test_logger_ring_bounded() -> None:
    log = setup_logger("saqr.test_reliability")
    ring = get_log_ring("saqr.test_reliability")
    for i in range(1100):
        log.info("line %s", i)
    assert len(ring) <= 1000


def test_env_defaults() -> None:
    assert max_spread_bps() > 0
    assert max_volatility_bps() > 0


def main() -> None:
    test_range_bps()
    test_loss_trip_fraction()
    test_logger_ring_bounded()
    test_env_defaults()
    print("OK: reliability layer smoke tests passed")


if __name__ == "__main__":
    main()
