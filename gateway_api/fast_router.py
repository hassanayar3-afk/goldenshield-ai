"""
Saqr sovereign local gateway — FastAPI + WebSocket (no neural engines in-process).
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_highway.bootstrap import setup_sovereign_root
from data_highway.runtime_env import (
    bind_host,
    bootstrap_environment,
    get_project_root,
    service_port,
    watchdog_enabled,
)
from risk_sentinel.control_state import engines_paused
from risk_sentinel.crash_watchdog import (
    register_restart_hook,
    run_supervised,
    start_watchdog,
    stop_watchdog,
    touch_event_loop_heartbeat,
)

setup_sovereign_root()
bootstrap_environment(ROOT)

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from data_highway.logging_config import setup_logger
from data_highway.sqlite_store import DatabaseManager
from gateway_api.binance_client import BinanceClient
from gateway_api.connection_manager import manager
from gateway_api.control_service import ControlService
from gateway_api.demo_seed import run_demo_seed_if_enabled
from gateway_api.recovery_service import RecoveryService
from gateway_api.stream_service import StreamService
from gateway_api.sync_service import SyncService
from gateway_api.user_stream import UserStreamService
from risk_sentinel.circuit_breaker import GlobalCircuitBreaker

logger = setup_logger("saqr.gateway")

db = DatabaseManager()
client = BinanceClient()
stream = StreamService(hub=manager)
sync = SyncService(db, client, manager, stream=stream)
control = ControlService(db, client, stream, manager, sync=sync)
circuit_breaker = GlobalCircuitBreaker(db, client, stream, control, manager)
sync.set_circuit_breaker(circuit_breaker)
recovery = RecoveryService(db, client, manager, stream)
user_stream = UserStreamService(db, client, manager)

_stream_task: Optional[asyncio.Task] = None
_user_stream_task: Optional[asyncio.Task] = None
_sync_task: Optional[asyncio.Task] = None


async def _graceful_restart() -> None:
    touch_event_loop_heartbeat()
    await recovery.run_boot_recovery()
    await manager.publish({"type": "watchdog", "action": "graceful_restart"})
    logger.warning("Graceful restart completed with recovery pass")


async def _start_background_services() -> None:
    global _stream_task, _user_stream_task, _sync_task
    db.connect()
    await client.start()
    ok = await client.ping()
    logger.info(
        "Gateway online — Binance ping=%s paper=%s mode=%s",
        ok,
        client.paper_trading,
        client.execution_mode,
    )
    await manager.start_heartbeat(interval=1.0)
    await recovery.run_boot_recovery()
    await control.load_runtime_flags()
    await circuit_breaker.load_state()
    try:
        await stream.warm_start(client)
    except Exception as exc:
        logger.warning("Stream warm_start failed: %s", exc)

    _stream_task = asyncio.create_task(
        run_supervised("stream_service", stream.run_forever),
        name="stream",
    )
    _user_stream_task = asyncio.create_task(
        run_supervised("user_stream", user_stream.run_forever),
        name="user-stream",
    )
    _sync_task = asyncio.create_task(
        run_supervised("sync_service", sync.run_forever),
        name="sync",
    )

    try:
        seeded = await run_demo_seed_if_enabled(db, client, stream, manager)
        if seeded:
            await sync.sync_once()
            logger.info("Demo seed: %s positions synced", seeded)
    except Exception as exc:
        logger.warning("Demo seed skipped: %s", exc)

    register_restart_hook(_graceful_restart)
    if watchdog_enabled():
        start_watchdog()
    await manager.publish({"type": "system", "status": "online", "paper_trading": client.paper_trading})


async def _stop_background_services() -> None:
    global _stream_task, _user_stream_task, _sync_task
    sync.stop()
    stream.stop()
    user_stream.stop()
    await user_stream.shutdown()
    tasks = [t for t in (_stream_task, _user_stream_task, _sync_task) if t]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _stream_task = None
    _user_stream_task = None
    _sync_task = None
    await manager.stop_heartbeat()
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


app = FastAPI(title="Saqr Sovereign Gateway", version="2.0.0", lifespan=lifespan)

UI_DIR = ROOT / "terminal_control"
if UI_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


def _control_panel() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/")
async def index() -> FileResponse:
    return _control_panel()


@app.get("/dashboard")
@app.get("/control")
async def dashboard_aliases() -> FileResponse:
    """Web control panel (same as /)."""
    return _control_panel()


@app.get("/health")
async def health() -> Dict[str, Any]:
    touch_event_loop_heartbeat()
    return {
        "status": "ok",
        "paper_trading": client.paper_trading,
        "root": str(get_project_root()),
        "bind_host": bind_host(),
        "port": service_port(8000),
        "hub": manager.snapshot(),
        "stream": stream.snapshot(),
        "sync": sync.last_snapshot.get("synced_at"),
    }


@app.get("/api/state")
async def api_state() -> Dict[str, Any]:
    positions = await db.list_positions_async()
    wins, losses = await db.closed_trade_counts_async()
    return {
        "positions": [p.__dict__ for p in positions],
        "protection_orders": await db.list_protection_orders_async(),
        "closed_trades": await db.list_closed_trades_async(50),
        "wins": wins,
        "losses": losses,
        "engines_paused": engines_paused(),
        "sync": sync.last_snapshot,
        "recovery": recovery.last_report,
        "hub": manager.snapshot(),
        "stream": stream.snapshot(),
    }


@app.post("/api/internal/publish")
async def internal_publish(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="local_only")
    await manager.broadcast(payload)
    return {"status": "broadcasted"}


@app.post("/api/recovery/run")
async def api_recovery_run() -> Dict[str, Any]:
    touch_event_loop_heartbeat()
    return await recovery.run_boot_recovery()


@app.post("/api/control/{action}")
async def api_control(action: str) -> Dict[str, Any]:
    touch_event_loop_heartbeat()
    return await control.handle_ui_action(action.replace("-", "_"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            touch_event_loop_heartbeat()
            data = await websocket.receive_text()
            await control.handle_ws_message(data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WS session error: %s", exc)
        await manager.disconnect(websocket)
