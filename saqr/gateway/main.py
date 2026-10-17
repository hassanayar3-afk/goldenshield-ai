"""
Saqr local gateway — FastAPI server, live WebSocket, engine orchestration.
Run from project root: python gateway/main.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Bootstrap paths before any saqr package imports ---
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.runtime_env import (
    bind_host,
    bootstrap_environment,
    bot_force_active,
    get_project_root,
    service_port,
    tri_commander_enabled,
    watchdog_enabled,
)

bootstrap_environment(ROOT)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database.db_manager import DatabaseManager
from engines.gold_flash import GoldFlashEngine
from engines.momentum import MomentumEngine
from engines.smc_macro import SmcMacroEngine
from gateway.binance_client import BinanceClient
from gateway.connection_manager import get_connection_manager_sync
from gateway.recovery_service import RecoveryService
from gateway.stream_service import StreamService
from gateway.sync_service import SyncService
from gateway.user_stream import UserStreamService
from utils.crash_wrapper import (
    register_restart_hook,
    run_supervised,
    start_watchdog,
    stop_watchdog,
    touch_event_loop_heartbeat,
)
from utils.logger_config import setup_logger
logger = setup_logger("saqr.gateway")

db = DatabaseManager()
hub = get_connection_manager_sync()
client = BinanceClient()
stream = StreamService(hub=hub)
sync = SyncService(db, client, hub)
recovery = RecoveryService(db, client, hub, stream)
user_stream = UserStreamService(db, client, hub)

_engine_tasks: List[asyncio.Task] = []
_stream_task: Optional[asyncio.Task] = None
_user_stream_task: Optional[asyncio.Task] = None


async def _graceful_restart() -> None:
    touch_event_loop_heartbeat()
    await recovery.run_boot_recovery()
    await hub.publish({"type": "watchdog", "action": "graceful_restart"})
    logger.warning("Graceful restart completed with recovery pass")


async def _start_background_services() -> None:
    global _engine_tasks, _stream_task, _user_stream_task
    db.connect()
    await client.start()
    ok = await client.ping()
    logger.info("Binance connectivity: %s (paper=%s)", ok, client.paper_trading)
    await hub.start_heartbeat(interval=1.0)
    await recovery.run_boot_recovery()

    _stream_task = asyncio.create_task(
        run_supervised("stream_service", stream.run_forever),
        name="stream",
    )
    _user_stream_task = asyncio.create_task(
        run_supervised("user_stream", user_stream.run_forever),
        name="user-stream",
    )

    engines = []
    if tri_commander_enabled() and bot_force_active():
        engines = [
            SmcMacroEngine(db, client, hub, stream),
            GoldFlashEngine(db, client, hub, stream),
            MomentumEngine(db, client, hub, stream),
        ]
    elif not bot_force_active():
        logger.warning("BOT_FORCE_ACTIVE=false — engines idle")
    else:
        logger.warning("TRI_COMMANDER_MODE=false — engines idle")

    _engine_tasks = [
        asyncio.create_task(run_supervised(e.name, e.run_forever), name=f"engine-{e.name}")
        for e in engines
    ]
    _engine_tasks.append(
        asyncio.create_task(run_supervised("sync_service", sync.run_forever), name="sync")
    )

    register_restart_hook(_graceful_restart)
    if watchdog_enabled():
        start_watchdog()
    await hub.publish({"type": "system", "status": "online", "paper_trading": client.paper_trading})


async def _stop_background_services() -> None:
    global _engine_tasks, _stream_task, _user_stream_task
    sync.stop()
    stream.stop()
    user_stream.stop()
    await user_stream.shutdown()
    tasks = [*_engine_tasks]
    if _stream_task:
        tasks.append(_stream_task)
    if _user_stream_task:
        tasks.append(_user_stream_task)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _engine_tasks = []
    _stream_task = None
    _user_stream_task = None
    await hub.stop_heartbeat()
    stop_watchdog()
    await client.close()
    db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _start_background_services()
    try:
        yield
    finally:
        await _stop_background_services()


app = FastAPI(title="Saqr AI Local Gateway", version="1.3.0", lifespan=lifespan)

UI_DIR = ROOT / "terminal_ui"
if UI_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/health")
async def health() -> Dict[str, Any]:
    touch_event_loop_heartbeat()
    return {
        "status": "ok",
        "paper_trading": client.paper_trading,
        "root": str(get_project_root()),
        "saqr_root": os.getenv("SAqr_ROOT"),
        "bind_host": bind_host(),
        "port": service_port(8000),
        "hub": hub.snapshot(),
        "stream": stream.snapshot(),
        "user_stream": user_stream.snapshot(),
        "recovery": recovery.last_report.get("recovered_at"),
        "sync": sync.last_snapshot.get("synced_at"),
    }


@app.get("/api/state")
async def api_state() -> Dict[str, Any]:
    positions = await db.list_positions_async()
    return {
        "positions": [p.__dict__ for p in positions],
        "protection_orders": await db.list_protection_orders_async(),
        "sync": sync.last_snapshot,
        "recovery": recovery.last_report,
        "hub": hub.snapshot(),
        "stream": stream.snapshot(),
        "user_stream": user_stream.snapshot(),
    }


@app.post("/api/recovery/run")
async def api_recovery_run() -> Dict[str, Any]:
    touch_event_loop_heartbeat()
    return await recovery.run_boot_recovery()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await hub.connect(websocket)
    try:
        while True:
            touch_event_loop_heartbeat()
            msg = await websocket.receive_text()
            if msg.strip().lower() == "ping":
                await hub.publish({"type": "pong"})
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    except Exception as exc:
        logger.warning("WS session error: %s", exc)
        await hub.disconnect(websocket)


def main() -> None:
    import uvicorn

    host = bind_host()
    port = service_port(8000)
    logger.info("Project root: %s", ROOT)
    logger.info("Starting Saqr (HTTP + WebSocket /ws) on http://%s:%s", host, port)
    if host == "0.0.0.0":
        logger.info("LAN: http://<laptop-ip>:%s", port)
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
