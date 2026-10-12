"""Router مركزي — GET/POST/PUT."""

from __future__ import annotations

import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from terminal_app.http.json_io import read_json_body, send_json
from terminal_app.routes import api_act, api_pair, api_public, api_read, api_upload, downloads, panel_static


def handle_get(handler: BaseHTTPRequestHandler) -> None:
    path = urlparse(handler.path).path
    try:
        if downloads.handle_download_get(handler, path):
            return
        if panel_static.handle_panel_get(handler, path):
            return
        if api_public.handle_public_get(handler, path):
            return
        if api_read.handle_authenticated_get(handler, path):
            return
        send_json(handler, 404, {"ok": False, "error": "not found"})
    except Exception as exc:
        send_json(
            handler,
            500,
            {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-500:]},
        )


def handle_post(handler: BaseHTTPRequestHandler) -> None:
    path = urlparse(handler.path).path
    try:
        body = read_json_body(handler)
        if path in ("/api/pair/web-auto", "/api/web-auto-pair"):
            if api_pair.handle_web_auto_pair_post(handler, body):
                return
        if path == "/api/pair":
            if api_pair.handle_pair_post(handler, body):
                return
        from terminal_app.http.auth_adapter import auth_ok

        if not auth_ok(handler):
            send_json(handler, 401, {"ok": False, "error": "unauthorized"})
            return
        if path in ("/api/discord/config", "/api/discord"):
            from terminal_app.services import bot_bridge as bb

            result = bb.save_discord_config(body)
            send_json(handler, 200 if result.get("ok") else 400, result)
            return
        if path == "/api/heartbeat":
            if api_act.handle_heartbeat_post(handler, body):
                return
        if path == "/api/act":
            if api_act.handle_act_post(handler, body):
                return
        send_json(handler, 404, {"ok": False, "error": "not found"})
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": str(exc)})


def handle_put(handler: BaseHTTPRequestHandler) -> None:
    path = urlparse(handler.path).path
    try:
        if api_upload.handle_upload_put(handler, path):
            return
        send_json(handler, 404, {"ok": False, "error": "not found"})
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": str(exc)})
