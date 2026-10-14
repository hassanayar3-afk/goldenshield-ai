#!/usr/bin/env python3
"""
Master consensus controller — supervises tri-commanders without cross-contamination.
Additive entrypoint: PM2 GS-NeuralCore or python core_engine/neural_matrix.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path


def _bootstrap_root() -> None:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    root = Path(raw)
    if root.is_dir():
        os.chdir(root)
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))


_bootstrap_root()

from deploy_ops.logging_config import configure_sovereign_logging  # noqa: E402

log = configure_sovereign_logging("gs_neural_matrix")


async def _validate_binance_keys() -> bool:
    try:
        from config.settings import get_settings

        s = get_settings()
        ok = bool(getattr(s, "binance_api_key", None) and getattr(s, "binance_api_secret", None))
        if not ok:
            log.warning("Binance keys missing — demo/paper may still run")
        return ok
    except Exception as exc:
        log.warning("key validation skip: %s", exc)
        return False


async def _watchdog_loop(last_tick: list[float]) -> None:
    stall_sec = float(os.getenv("GS_EVENT_LOOP_STALL_SEC", "30") or 30)
    while True:
        await asyncio.sleep(5)
        idle = time.monotonic() - last_tick[0]
        if idle > stall_sec:
            log.error("event loop stall %.1fs — requesting safe recycle", idle)
            try:
                from risk_sentinel.sovereign_guard import notify_discord_emergency

                notify_discord_emergency(f"Neural matrix stall {idle:.0f}s")
            except Exception:
                pass
            last_tick[0] = time.monotonic()


async def _consensus_cycle() -> None:
    from data_highway.zero_copy_cache import publish, remember_idempotent
    from terminal.orchestrator import TriCommanderOrchestrator, tri_commander_enabled

    if not tri_commander_enabled():
        log.info("TRI_COMMANDER_MODE off — neural matrix idle")
        while True:
            await asyncio.sleep(30)
    orch = TriCommanderOrchestrator.create_default()
    symbols = (os.getenv("NEURAL_MATRIX_SYMBOLS") or "BTCUSDT,ETHUSDT").split(",")
    symbols = [s.strip().upper() for s in symbols if s.strip()]
    proposals = orch.collect_proposals(symbols)
    key = f"matrix:{len(proposals)}:{symbols[:3]}"
    if remember_idempotent(key, ttl_sec=2.0):
        publish({"type": "consensus", "proposals": len(proposals), "symbols": len(symbols)})
    log.debug("consensus proposals=%s", len(proposals))


async def run_matrix_supervisor() -> None:
    await _validate_binance_keys()
    last_tick = [time.monotonic()]
    asyncio.create_task(_watchdog_loop(last_tick))
    log.info("Neural matrix supervisor online")
    while True:
        last_tick[0] = time.monotonic()
        try:
            await _consensus_cycle()
        except Exception as exc:
            log.exception("consensus cycle: %s", exc)
        await asyncio.sleep(float(os.getenv("NEURAL_MATRIX_INTERVAL_SEC", "4") or 4))


def main() -> None:
    if os.getenv("GS_NEURAL_RUN_MAIN_BOT", "false").lower() in {"1", "true", "yes"}:
        try:
            from main import run_bot

            log.info("Delegating to main.run_bot (full stack)")
            asyncio.run(run_bot())
            return
        except Exception as exc:
            log.warning("main.run_bot failed (%s) — fallback supervisor loop", exc)
    asyncio.run(run_matrix_supervisor())


if __name__ == "__main__":
    main()
