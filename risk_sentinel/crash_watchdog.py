"""
Global crash-proof async wrapper and event-loop stall watchdog (30s graceful restart).
"""

from __future__ import annotations

import asyncio
import functools
import os
import threading
import time
import traceback
from typing import Any, Awaitable, Callable, Optional, TypeVar

from data_highway.logging_config import setup_logger

T = TypeVar("T")
logger = setup_logger("saqr.watchdog")

_last_loop_tick = time.monotonic()
_watchdog_thread: Optional[threading.Thread] = None
_watchdog_stop = threading.Event()
_restart_hook: Optional[Callable[[], Awaitable[None]]] = None
_last_graceful_restart = 0.0
_restart_in_flight = False


def touch_event_loop_heartbeat() -> None:
    """Call from the asyncio loop periodically to prove liveness."""
    global _last_loop_tick
    _last_loop_tick = time.monotonic()


def _stall_threshold_seconds() -> float:
    try:
        return float(os.getenv("WATCHDOG_STALL_SECONDS", "30"))
    except ValueError:
        return 30.0


def _restart_cooldown_seconds() -> float:
    try:
        return float(os.getenv("WATCHDOG_RESTART_COOLDOWN", "15"))
    except ValueError:
        return 15.0


def register_restart_hook(coro_factory: Callable[[], Awaitable[None]]) -> None:
    """Hook invoked when watchdog detects a frozen loop (graceful recovery)."""
    global _restart_hook
    _restart_hook = coro_factory


def _watchdog_loop() -> None:
    threshold = _stall_threshold_seconds()
    cooldown = _restart_cooldown_seconds()
    while not _watchdog_stop.is_set():
        time.sleep(1.0)
        stalled_for = time.monotonic() - _last_loop_tick
        if stalled_for <= threshold:
            continue
        if time.monotonic() - _last_graceful_restart < cooldown:
            continue
        logger.error(
            "Event loop stall detected (%.1fs > %.1fs); scheduling graceful restart",
            stalled_for,
            threshold,
        )
        if _restart_hook is None:
            continue
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_graceful_restart_once(), loop)
        except Exception as exc:
            logger.error("Watchdog restart scheduling failed: %s", exc)


async def _graceful_restart_once() -> None:
    global _last_graceful_restart, _restart_in_flight
    if _restart_in_flight:
        return
    _restart_in_flight = True
    try:
        touch_event_loop_heartbeat()
        if _restart_hook is not None:
            await _restart_hook()
        _last_graceful_restart = time.monotonic()
        logger.info("Graceful watchdog restart completed")
    except Exception as exc:
        logger.error("Graceful restart failed: %s", exc)
    finally:
        _restart_in_flight = False


def start_watchdog() -> None:
    global _watchdog_thread
    if _watchdog_thread and _watchdog_thread.is_alive():
        return
    _watchdog_stop.clear()
    touch_event_loop_heartbeat()
    _watchdog_thread = threading.Thread(
        target=_watchdog_loop,
        name="saqr-watchdog",
        daemon=True,
    )
    _watchdog_thread.start()
    logger.info("Internal health watchdog started")


def stop_watchdog() -> None:
    _watchdog_stop.set()


def crash_proof(
    *,
    component: str,
    restart_delay: float = 3.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[Optional[T]]]]:
    """Decorator: log fatal errors, sleep with jitter, and re-run the coroutine."""

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Optional[T]]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            while True:
                try:
                    touch_event_loop_heartbeat()
                    return await fn(*args, **kwargs)
                except asyncio.CancelledError:
                    logger.info("%s cancelled cleanly", component)
                    raise
                except Exception as exc:
                    logger.error(
                        "%s crashed: %s\n%s",
                        component,
                        exc,
                        traceback.format_exc(),
                    )
                    jitter = restart_delay * 0.2
                    await asyncio.sleep(restart_delay + (jitter * 0.5))

        return wrapper

    return decorator


async def run_supervised(
    name: str,
    coro_factory: Callable[[], Awaitable[None]],
    *,
    restart_delay: float = 3.0,
) -> None:
    """Run a long-lived coroutine with automatic restart on failure."""

    @crash_proof(component=name, restart_delay=restart_delay)
    async def _inner() -> None:
        await coro_factory()

    await _inner()
