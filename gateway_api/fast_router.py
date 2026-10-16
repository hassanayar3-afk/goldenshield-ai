#!/usr/bin/env python3
"""FastAPI gateway — health + live SSE; optional uvloop on Linux."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path


def _bootstrap() -> None:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    root = Path(raw)
    if root.is_dir():
        os.chdir(root)
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    try:
        from terminal_app.config import bootstrap

        bootstrap()
    except Exception:
        pass


_bootstrap()

try:
    if sys.platform != "win32":
        import uvloop

        uvloop.install()
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402

from deploy_ops.logging_config import configure_sovereign_logging  # noqa: E402
from terminal_app.routes.api_live import live_stream_auth_ok_token  # noqa: E402

log = configure_sovereign_logging("gs_gateway")
app = FastAPI(title="GoldenShield Gateway", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _verify_token(token: str) -> bool:
    try:
        return live_stream_auth_ok_token(token)
    except Exception:
        return False


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "service": "gs-gateway",
        "ts": time.time(),
    }


@app.get("/api/live/stream")
async def live_stream(token: str = Query("")) -> StreamingResponse:
    if not _verify_token(token):
        raise HTTPException(status_code=401, detail="unauthorized")

    try:
        ms = (os.getenv("GS_LIVE_INTERVAL_MS") or "").strip()
        if ms:
            interval = max(0.005, float(ms) / 1000.0)
        else:
            raw = float(os.getenv("LIVE_PANEL_INTERVAL_SEC", "1.0") or 1.0)
            floor = 0.005 if (os.getenv("GS_ULTRA_LIVE_STREAM", "false").lower() in {"1", "true", "yes"}) else 0.05
            interval = max(floor, raw)
    except Exception:
        interval = 1.0

    async def gen():
        while True:
            try:
                from terminal_app.routes.api_live import panel_live_tick

                tick = await asyncio.to_thread(panel_live_tick)
                payload = json.dumps(tick, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            except Exception as exc:
                log.debug("live tick: %s", exc)
            await asyncio.sleep(interval)

    return StreamingResponse(gen(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    port = int(os.getenv("GATEWAY_API_PORT", os.getenv("MOBILE_API_PORT", "8790")) or 8790)
    log.info("GS-Gateway listen %s", port)
    uvicorn.run(
        "gateway_api.fast_router:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
