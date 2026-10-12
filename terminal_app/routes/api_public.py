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
                "rules": bb.rules_payload(),
                "ws_port": int(__import__("os").getenv("TERMINAL_WS_PORT", "8791") or 8791),
                "auth_model": {
                    "strategy_code": "macro/scalp identity only (e.g. GS-GOLD80)",
                    "mobile_pair_code": "device pairing secret",
                    "device_token": "session auth via X-GS-Token after /api/pair",
                },
            },
        )
        return True
    return False
