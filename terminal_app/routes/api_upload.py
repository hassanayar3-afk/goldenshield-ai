"""PUT upload APK."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from pathlib import Path

from terminal_app.config import ROOT
from terminal_app.http.auth_adapter import auth_ok
from terminal_app.http.json_io import send_json
from terminal_app.services import mobile_core as core


def handle_upload_put(handler: BaseHTTPRequestHandler, path: str) -> bool:
    if path not in ("/upload/apk", "/api/upload/apk"):
        return False
    if not auth_ok(handler):
        send_json(handler, 401, {"ok": False, "error": "unauthorized"})
        return True
    length = int(handler.headers.get("Content-Length") or 0)
    if length < 100_000 or length > 80_000_000:
        send_json(handler, 400, {"ok": False, "error": f"bad size {length}"})
        return True
    raw = handler.rfile.read(length)
    if raw[:2] != b"PK":
        send_json(handler, 400, {"ok": False, "error": "not an apk/zip"})
        return True
    targets = [
        Path(r"C:\Users\Public\GoldenShield-Control.apk"),
        ROOT / "downloads" / "GoldenShield-Control.apk",
        ROOT / "storage" / "mobile" / "GoldenShield-Control.apk",
    ]
    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        except Exception:
            pass
    core._push_alert("apk", "تم تحديث APK", f"{length} بايت", level="ok")
    send_json(handler, 200, {"ok": True, "bytes": length})
    return True
