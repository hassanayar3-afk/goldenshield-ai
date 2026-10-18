"""
Neural core — tri-commander engines in a dedicated local process (SQLite + remote WS fan-out).
Run: python core_engine/neural_matrix.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_highway.bootstrap import setup_sovereign_root
from data_highway.runtime_env import (
    bootstrap_environment,
    bot_force_active,
    tri_commander_enabled,
    watchdog_enabled,
)
from risk_sentinel.crash_watchdog import (
    register_restart_hook,
    run_supervised,
    start_watchdog,
    stop_watchdog,
    touch_event_loop_heartbeat,
)

setup_sovereign_root()
bootstrap_environment(ROOT)

from core_engine.black_horse_smc import SmcMacroEngine
from core_engine.momentum_ioc import MomentumEngine
from core_engine.remote_hub import RemoteHub
from core_engine.zscore_flash import GoldFlashEngine
from data_highway.logging_config import setup_logger
from data_highway.sqlite_store import DatabaseManager
from gateway_api.binance_client import BinanceClient
from gateway_api.stream_service import StreamService

logger = setup_logger("saqr.neural_matrix")

_engine_tasks: List[asyncio.Task] = []
_stream_task: Optional[asyncio.Task] = None


async def _graceful_restart() -> None:
    touch_event_loop_heartbeat()
    logger.warning("Neural matrix graceful restart hook")


async def _run() -> None:
    global _engine_tasks, _stream_task
    db = DatabaseManager()
    hub = RemoteHub()
    client = BinanceClient()
    stream = StreamService(hub=hub)

    db.connect()
    await client.start()
    try:
        await stream.warm_start(client)
    except Exception as exc:
        logger.warning("Stream warm_start failed: %s", exc)

    _stream_task = asyncio.create_task(
        run_supervised("neural_stream", stream.run_forever),
        name="neural-stream",
    )

    engines = []
    if tri_commander_enabled() and bot_force_active():
        engines = [
            SmcMacroEngine(db, client, hub, stream),
            GoldFlashEngine(db, client, hub, stream),
            MomentumEngine(db, client, hub, stream),
        ]
    elif not bot_force_active():
        logger.warning("BOT_FORCE_ACTIVE=false — neural matrix idle")
    else:
        logger.warning("TRI_COMMANDER_MODE=false — neural matrix idle")

    _engine_tasks = [
        asyncio.create_task(run_supervised(e.name, e.run_forever), name=f"engine-{e.name}")
        for e in engines
    ]

    register_restart_hook(_graceful_restart)
    if watchdog_enabled():
        start_watchdog()

    logger.info("Neural matrix running (%s engines)", len(engines))
    await asyncio.gather(_stream_task, *_engine_tasks)


async def _shutdown() -> None:
    stop_watchdog()
    for task in _engine_tasks:
        task.cancel()
    if _stream_task:
        _stream_task.cancel()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Neural matrix stopped")


if __name__ == "__main__":
    main()
