"""Forward engine events to the local gateway process (127.0.0.1)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import aiohttp

from data_highway.logging_config import setup_logger

logger = setup_logger("saqr.remote_hub")


class RemoteHub:
    """Minimal ConnectionManager-compatible publisher for the neural core process."""

    def __init__(self, publish_url: Optional[str] = None) -> None:
        port = os.getenv("TERMINAL_WS_PORT", os.getenv("MOBILE_API_PORT", "8000"))
        default = f"http://127.0.0.1:{port}/api/internal/publish"
        self._url = publish_url or os.getenv("GATEWAY_PUBLISH_URL", default)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def publish(self, payload: Dict[str, Any]) -> None:
        try:
            session = await self._session_get()
            async with session.post(self._url, json=payload, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status >= 400:
                    logger.warning("Remote publish HTTP %s", resp.status)
        except Exception as exc:
            logger.debug("Remote publish skipped: %s", exc)

    async def start_heartbeat(self, interval: float = 1.0) -> None:
        return None

    async def stop_heartbeat(self) -> None:
        return None

    def snapshot(self) -> Dict[str, Any]:
        return {"remote_hub": True, "url": self._url}

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
