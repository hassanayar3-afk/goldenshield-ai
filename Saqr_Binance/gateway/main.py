"""
Saqr local gateway — FastAPI server, live WebSocket, kline stream, engine orchestration.
Run: python -m gateway.main  (from C:\\Saqr_Binance)
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
_saqr_root = os.getenv("SAqr_ROOT")
if _saqr_root:
    load_dotenv(Path(_saqr_root) / ".env", override=True)

from database.db_manager import DatabaseManager  # noqa: E402
from engines.gold_flash import GoldFlashEngine  # noqa: E402
from engines.momentum import MomentumEngine  # noqa: E402
from engines.smc_macro import SmcMacroEngine  # noqa: E402
from gateway.binance_client import BinanceClient  # noqa: E402
from gateway.connection_manager import get_connection_manager_sync  # noqa: E402
from gateway.recovery_service import RecoveryService  # noqa: E402
from gateway.stream_service import StreamService  # noqa: E402
from gateway.sync_service import SyncService  # noqa: E402
from gateway.user_stream import UserStreamService  # noqa: E402
from utils.crash_wrapper import (  # noqa: E402
    register_restart_hook,
    run_supervised,
    start_watchdog,
    stop_watchdog,
    touch_event_loop_heartbeat,
)
from utils.logger_config import setup_logger  # noqa: E402
from utils.runtime_env import service_port, watchdog_enabled  # noqa: E402

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
    """Watchdog recovery: persist state, keep DB open, nudge live services."""
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

    engines = [
        SmcMacroEngine(db, client, hub, stream),
        GoldFlashEngine(db, client, hub, stream),
        MomentumEngine(db, client, hub, stream),
    ]
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


app = FastAPI(title="Saqr AI Local Gateway", version="1.2.0", lifespan=lifespan)

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

    host = "0.0.0.0" if os.getenv("MOBILE_WEB_DIRECT_ACCESS", "").lower() in ("1", "true", "yes") else "127.0.0.1"
    port = service_port(8000)
    logger.info("Starting Saqr gateway on http://%s:%s", host, port)
    uvicorn.run(
        "gateway.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
