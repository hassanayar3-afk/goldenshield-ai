"""ربط http.server بالـ TokenGuard."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from terminal_app.auth.pocket_touch_lock import PocketTouchLock
from terminal_app.auth.token_guard import TokenGuard
from terminal_app.config import MASTER_TOKEN
from terminal_app.services import mobile_core as core


class HandlerAuthAdapter:
    def __init__(self, handler: BaseHTTPRequestHandler) -> None:
        self._handler = handler

    @property
    def path(self) -> str:
        return self._handler.path

    def headers_get(self, name: str, default: str = "") -> str:
        return self._handler.headers.get(name, default)


def token_guard() -> TokenGuard:
    return TokenGuard(
        master_token=MASTER_TOKEN,
        devices_loader=lambda: core._devices(),
        allow_query_token=False,
    )


def pocket_lock() -> PocketTouchLock:
    return PocketTouchLock(token_guard=token_guard())


def auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    try:
        return token_guard().verify(HandlerAuthAdapter(handler)).ok
    except Exception:
        token = handler.headers.get("X-GS-Token") or handler.headers.get(
            "Authorization", ""
        ).replace("Bearer ", "")
        if token == MASTER_TOKEN:
            return True
        devices = core._devices().get("devices", {})
        return token in devices
