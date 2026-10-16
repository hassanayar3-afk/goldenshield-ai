"""لوحة التحكم control-panel-www."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

import os

from terminal_app.config import PANEL_ROOT, PAIR_CODE, PORT
from terminal_app.http.json_io import send_cors, send_json


def _serve_panel_file(handler: BaseHTTPRequestHandler, rel: str) -> bool:
    rel = (rel or "index.html").replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        send_json(handler, 400, {"ok": False, "error": "bad path"})
        return True
    target = (PANEL_ROOT / rel).resolve()
    try:
        target.relative_to(PANEL_ROOT.resolve())
    except Exception:
        send_json(handler, 400, {"ok": False, "error": "bad path"})
        return True
    if target.is_dir():
        target = target / "index.html"
    if not target.exists() or not target.is_file():
        send_json(handler, 404, {"ok": False, "error": f"not found: {rel}"})
        return True
    raw = target.read_bytes()
    suffix = target.suffix.lower()
    ctype = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".ico": "image/x-icon",
        ".woff2": "font/woff2",
        ".map": "application/json",
    }.get(suffix, "application/octet-stream")
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    send_cors(handler)
    handler.end_headers()
    handler.wfile.write(raw)
    return True


def _client_is_local(handler: BaseHTTPRequestHandler) -> bool:
    try:
        host = (handler.headers.get("Host") or "").split(":")[0].strip().lower()
        if host in {"127.0.0.1", "localhost", "::1"}:
            return True
        fwd = (handler.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return fwd in {"127.0.0.1", "::1"}
    except Exception:
        return False


def _serve_panel_boot_js(handler: BaseHTTPRequestHandler) -> bool:
    web_auto = os.getenv("MOBILE_WEB_DIRECT_ACCESS", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    local = _client_is_local(handler)
    body = (
        "window.GS_PANEL_BOOT="
        + __import__("json").dumps(
            {
                "pair_code": PAIR_CODE,
                "mobile_pair_code": PAIR_CODE,
                "web_direct_access": web_auto,
                "local_preview": local,
                "auto_pair": True,
                "api_port": int(os.getenv("MOBILE_API_PORT", str(PORT)) or PORT),
            },
            ensure_ascii=False,
        )
        + ";\n"
    ).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    send_cors(handler)
    handler.end_headers()
    handler.wfile.write(body)
    return True


def handle_panel_get(handler: BaseHTTPRequestHandler, path: str) -> bool:
    from terminal_app.services import alerts_queue as aq
    from terminal_app.services import bot_bridge as bb

    if path == "/js/panel_boot.js":
        return _serve_panel_boot_js(handler)

    if path in ("/", "/panel", "/panel/", "/dashboard", "/dashboard/"):
        index = PANEL_ROOT / "index.html"
        if index.exists():
            return _serve_panel_file(handler, "index.html")
        send_json(
            handler,
            200,
            {
                "ok": True,
                "service": "goldenshield-mobile-api",
                        "ts": aq.utc(),
                "hint": "control panel not installed — open /api/health",
                "pair_code_hint": PAIR_CODE[:3] + "***",
            },
        )
        return True
    if path.startswith("/panel/") or path.startswith("/dashboard/"):
        rel = path.split("/", 2)[-1]
        return _serve_panel_file(handler, rel)
    if path.startswith(("/ui/", "/config/", "/controllers/", "/services/", "/notifications/", "/js/")) or path in (
        "/boot.js",
        "/index.html",
    ):
        return _serve_panel_file(handler, path.lstrip("/"))
    return False
