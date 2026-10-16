"""Async-friendly Binance lane — delegates to existing clients without blocking the loop."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


async def run_blocking(func: Callable[..., Any], *args: object, **kwargs: object) -> Any:
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except Exception as exc:
        logger.warning("binance_async_lane: %s", exc)
        raise
