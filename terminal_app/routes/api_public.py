"""مسارات عامة — health / bootstrap."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from terminal_app.config import PAIR_CODE, STRATEGY_CODE
from terminal_app.http.json_io import send_json
from terminal_app.services import alerts_queue as aq
from terminal_app.services import bot_bridge as bb


def handle_public_get(handler: BaseHTTPRequestHandler, path: str) -> bool:
    if path == "/api/health":
        send_json(
            handler,
            200,
            {"ok": True, "service": "goldenshield-mobile-api", "ts": aq.utc()},
        )
        return True
    if path in ("/api/bootstrap", "/api/boot"):
        tun = bb.tunnel_url().lstrip("\ufeff").strip()
        send_json(
            handler,
            200,
            {
                "ok": True,
                "service": "goldenshield-mobile-api",
                "ts": aq.utc(),
                "strategy_code": STRATEGY_CODE,
                "pair_code": PAIR_CODE,
                "mobile_pair_code": PAIR_CODE,
                "pair_code_hint": PAIR_CODE[:3] + "***",
                "api_base_hint": tun.rstrip("/") if tun.startswith("https://") else "",
                "tunnel_url": tun.rstrip("/") + "/" if tun.startswith("http") else "",
                "rules": bb.rules_payload(),
                "ws_port": int(__import__("os").getenv("TERMINAL_WS_PORT", "8791") or 8791),
                "web_direct_access": (
                    __import__("os").getenv("MOBILE_WEB_DIRECT_ACCESS", "true").lower()
                    not in {"0", "false", "no", "off"}
                ),
                "auth_model": {
                    "strategy_code": "macro/scalp identity only (e.g. GS-GOLD80)",
                    "mobile_pair_code": "device pairing secret",
                    "device_token": "session auth via X-GS-Token after /api/pair",
                },
            },
        )
        return True
    if path == "/api/mobile/config":
        import os as _os

        tun = bb.tunnel_url().lstrip("\ufeff").strip().rstrip("/")
        port = int(_os.getenv("MOBILE_API_PORT", "8790") or 8790)
        base = tun if tun.startswith("http") else f"http://127.0.0.1:{port}"
        send_json(
            handler,
            200,
            {
                "ok": True,
                "ts": aq.utc(),
                "tunnel_url": (tun + "/") if tun else "",
                "local_api_base": f"http://127.0.0.1:{port}/",
                "ws_port": int(_os.getenv("TERMINAL_WS_PORT", "8791") or 8791),
                "paths": {
                    "bootstrap": "/api/bootstrap",
                    "live_base": "/download/live-base",
                    "apk": "/download/apk",
                    "stack": "/api/stack",
                },
                "apk_download": (base.rstrip("/") + "/download/apk") if base else "",
                "tri_commander_mode": (_os.getenv("TRI_COMMANDER_MODE", "true").lower() not in {"0", "false", "no"}),
            },
        )
        return True
    return False
