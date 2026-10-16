"""مسارات عامة — health / bootstrap."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

import os
import urllib.parse

import time
from pathlib import Path

from terminal_app.config import PAIR_CODE, PORT, RUNTIME, STRATEGY_CODE
from terminal_app.http.json_io import send_json
from terminal_app.services import alerts_queue as aq
from terminal_app.services import bot_bridge as bb


def _client_is_local(handler: BaseHTTPRequestHandler) -> bool:
    try:
        host = (handler.headers.get("Host") or "").split(":")[0].strip().lower()
        if host in {"127.0.0.1", "localhost", "::1"}:
            return True
        fwd = (handler.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return fwd in {"127.0.0.1", "::1"}
    except Exception:
        return False


def pair_link_payload() -> dict:
    """روابط لوحة التحكم مع رمز الربط في query (للمتصفح / WebView)."""
    tun = bb.tunnel_url().lstrip("\ufeff").strip().rstrip("/")
    code = PAIR_CODE
    q = urllib.parse.urlencode({"pair_code": code})
    panel = f"{tun}/?{q}" if tun.startswith("http") else ""
    host = (
        os.getenv("MOBILE_PUBLIC_IP")
        or os.getenv("GS_PANEL_PUBLIC_HOST")
        or os.getenv("WIN_HOST")
        or ""
    ).strip()
    ip_panel = f"http://{host}:{PORT}/?{q}" if host else ""
    return {
        "pair_code": code,
        "mobile_pair_code": code,
        "panel_pair_url": panel,
        "ip_panel_pair_url": ip_panel,
        "pair_query": q,
        "note_ip": (
            "ip_panel_pair_url يعمل داخل شبكة السيرفر أو RDP؛ "
            "8790 غالباً غير مفتوح من الإنترنت — استخدم panel_pair_url."
        ),
    }


def handle_public_get(handler: BaseHTTPRequestHandler, path: str) -> bool:
    if path == "/api/health":
        snap_age = None
        hb_age = None
        try:
            snap_path = Path(RUNTIME) / "binance_snapshot.json"
            if snap_path.is_file():
                snap_age = round(time.time() - snap_path.stat().st_mtime, 1)
        except Exception:
            pass
        try:
            hb_path = Path(RUNTIME) / "heartbeat.json"
            if hb_path.is_file():
                hb_age = round(time.time() - hb_path.stat().st_mtime, 1)
        except Exception:
            pass
        spinal_ok = snap_age is not None and snap_age < 120.0
        send_json(
            handler,
            200,
            {
                "ok": True,
                "service": "goldenshield-mobile-api",
                "ts": aq.utc(),
                "port": PORT,
                "spinal": {
                    "snapshot_age_sec": snap_age,
                    "heartbeat_age_sec": hb_age,
                    "snapshot_fresh": spinal_ok,
                },
            },
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
                "local_preview": _client_is_local(handler),
                "auto_pair": True,
                "auth_model": {
                    "strategy_code": "macro/scalp identity only (e.g. GS-GOLD80)",
                    "mobile_pair_code": "device pairing secret",
                    "device_token": "session auth via X-GS-Token after /api/pair",
                },
                **pair_link_payload(),
            },
        )
        return True
    if path == "/api/mobile/pair-link":
        send_json(handler, 200, {"ok": True, "ts": aq.utc(), **pair_link_payload()})
        return True
    if path == "/api/mobile/config":
        tun = bb.tunnel_url().lstrip("\ufeff").strip().rstrip("/")
        port = int(os.getenv("MOBILE_API_PORT", "8790") or 8790)
        base = tun if tun.startswith("http") else f"http://127.0.0.1:{port}"
        send_json(
            handler,
            200,
            {
                "ok": True,
                "ts": aq.utc(),
                "tunnel_url": (tun + "/") if tun else "",
                "local_api_base": f"http://127.0.0.1:{port}/",
                "ws_port": int(os.getenv("TERMINAL_WS_PORT", "8791") or 8791),
                "live_stream": "/api/live/stream",
                "live_interval_sec": float(os.getenv("LIVE_PANEL_INTERVAL_SEC", "1.0") or 1.0),
                "paths": {
                    "bootstrap": "/api/bootstrap",
                    "live_base": "/download/live-base",
                    "live_stream": "/api/live/stream",
                    "apk": "/download/apk",
                    "stack": "/api/stack",
                },
                "apk_download": (base.rstrip("/") + "/download/apk") if base else "",
                "tri_commander_mode": (
                    os.getenv("TRI_COMMANDER_MODE", "true").lower() not in {"0", "false", "no"}
                ),
                **pair_link_payload(),
            },
        )
        return True
    return False
