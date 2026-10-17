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

from database.db_manager import DatabaseManager  # noqa: E402
from engines.gold_flash import GoldFlashEngine  # noqa: E402
from engines.momentum import MomentumEngine  # noqa: E402
from engines.smc_macro import SmcMacroEngine  # noqa: E402
from gateway.binance_client import BinanceClient  # noqa: E402
from gateway.connection_manager import get_connection_manager_sync  # noqa: E402
from gateway.stream_service import StreamService  # noqa: E402
from gateway.sync_service import SyncService  # noqa: E402
from utils.crash_wrapper import (  # noqa: E402
    register_restart_hook,
    run_supervised,
    start_watchdog,
    stop_watchdog,
    touch_event_loop_heartbeat,
)
from utils.logger_config import setup_logger  # noqa: E402

logger = setup_logger("saqr.gateway")

db = DatabaseManager()
hub = get_connection_manager_sync()
client = BinanceClient()
stream = StreamService(hub=hub)
sync = SyncService(db, client, hub)

_engine_tasks: List[asyncio.Task] = []
_stream_task: Optional[asyncio.Task] = None


async def _graceful_restart() -> None:
    """Watchdog recovery: persist state, keep DB open, nudge live services."""
    touch_event_loop_heartbeat()
    await hub.publish({"type": "watchdog", "action": "graceful_restart"})
    logger.warning("Graceful restart signal emitted — event loop nudged")


async def _start_background_services() -> None:
    global _engine_tasks, _stream_task
    db.connect()
    await client.start()
    ok = await client.ping()
    logger.info("Binance connectivity: %s (paper=%s)", ok, client.paper_trading)
    await hub.start_heartbeat(interval=1.0)

    _stream_task = asyncio.create_task(
        run_supervised("stream_service", stream.run_forever),
        name="stream",
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
    start_watchdog()
    await hub.publish({"type": "system", "status": "online", "paper_trading": client.paper_trading})


async def _stop_background_services() -> None:
    global _engine_tasks, _stream_task
    sync.stop()
    stream.stop()
    for task in [*_engine_tasks, *([_stream_task] if _stream_task else [])]:
        task.cancel()
    if _engine_tasks or _stream_task:
        await asyncio.gather(
            *(_engine_tasks + ([_stream_task] if _stream_task else [])),
            return_exceptions=True,
        )
    _engine_tasks = []
    _stream_task = None
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


app = FastAPI(title="Saqr AI Local Gateway", version="1.1.0", lifespan=lifespan)

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
        "sync": sync.last_snapshot.get("synced_at"),
    }


@app.get("/api/state")
async def api_state() -> Dict[str, Any]:
    positions = await db.list_positions_async()
    return {
        "positions": [p.__dict__ for p in positions],
        "sync": sync.last_snapshot,
        "hub": hub.snapshot(),
        "stream": stream.snapshot(),
    }


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

    host = os.getenv("GATEWAY_HOST", "127.0.0.1")
    port = int(os.getenv("GATEWAY_PORT", "8000"))
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
