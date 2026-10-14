"""بث حي للوحة — Server-Sent Events على نفس منفذ Mobile API (8790)."""

from __future__ import annotations

import json
import os
import time
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from terminal_app.http.auth_adapter import token_guard
from terminal_app.http.json_io import send_cors, send_json
from terminal_app.services import alerts_queue as aq
from terminal_app.services import binance_mirror as bm
from terminal_app.services import bot_bridge as bb


def _live_interval_sec() -> float:
    try:
        return max(0.5, float(os.getenv("LIVE_PANEL_INTERVAL_SEC", "1.0") or 1.0))
    except Exception:
        return 1.0


def _token_from_handler(handler: BaseHTTPRequestHandler) -> str:
    tok = (handler.headers.get("X-GS-Token") or "").strip()
    if tok:
        return tok
    auth = (handler.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    query = parse_qs(urlparse(handler.path).query)
    for key in ("token", "gs_token", "device_token"):
        vals = query.get(key) or []
        if vals and str(vals[0]).strip():
            return str(vals[0]).strip()
    return ""


def live_stream_auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    try:
        tok = _token_from_handler(handler)
        return live_stream_auth_ok_token(tok)
    except Exception:
        return False


def live_stream_auth_ok_token(tok: str) -> bool:
    try:
        if not (tok or "").strip():
            return False
        return token_guard().verify_raw_token(tok.strip()).ok
    except Exception:
        return False


def panel_live_tick() -> dict:
    try:
        bm.binance_snapshot(force=False)
    except Exception:
        pass
    status = bb.status()
    signals = bb.signals_live()
    positions = [p for p in bb.positions() if p and not p.get("dust")]
    pulse_ts = ""
    try:
        pulse = bb.RUNTIME / "last_cycle_signals.json"
        if pulse.exists():
            data = json.loads(pulse.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict) and data.get("ts"):
                pulse_ts = str(data["ts"])
    except Exception:
        pass
    return {
        "ok": True,
        "type": "tick",
        "ts": aq.utc(),
        "pulse_ts": pulse_ts,
        "status": status,
        "signals": signals,
        "positions": positions,
        "rules": bb.rules_payload(),
        "live": True,
    }


def handle_live_get(handler: BaseHTTPRequestHandler, path: str) -> bool:
    if path != "/api/live/stream":
        return False
    if not live_stream_auth_ok(handler):
        send_json(handler, 401, {"ok": False, "error": "unauthorized — pair first"})
        return True
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache, no-transform")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Accel-Buffering", "no")
        send_cors(handler)
        handler.end_headers()
        interval = _live_interval_sec()
        hello = json.dumps(
            {"ok": True, "type": "hello", "interval_sec": interval, "ts": aq.utc()},
            ensure_ascii=False,
        )
        handler.wfile.write(f"event: hello\ndata: {hello}\n\n".encode("utf-8"))
        handler.wfile.flush()
        while True:
            tick = panel_live_tick()
            body = json.dumps(tick, ensure_ascii=False)
            handler.wfile.write(f"event: tick\ndata: {body}\n\n".encode("utf-8"))
            handler.wfile.flush()
            time.sleep(interval)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    except Exception as exc:
        try:
            err = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            handler.wfile.write(f"event: error\ndata: {err}\n\n".encode("utf-8"))
            handler.wfile.flush()
        except Exception:
            pass
        aq.push_alert(
            "live_stream",
            "Live stream error",
            traceback.format_exc()[-400:],
            level="warn",
        )
    return True
