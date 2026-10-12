"""تنزيل APK / export / live-base."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from terminal_app.config import ROOT, RUNTIME
from terminal_app.http.json_io import send_cors, send_json
from terminal_app.services import bot_bridge as bb


def handle_download_get(handler: BaseHTTPRequestHandler, path: str) -> bool:
    if path in ("/download/export", "/download/source.zip", "/GoldenShield-Source-Export.zip"):
        archive = Path(r"C:\Users\Public\GoldenShield-Source-Export.zip")
        if not archive.exists():
            send_json(handler, 404, {"ok": False, "error": "export zip not found"})
            return True
        raw = archive.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/zip")
        handler.send_header(
            "Content-Disposition",
            "attachment; filename=GoldenShield-Source-Export.zip",
        )
        handler.send_header("Content-Length", str(len(raw)))
        send_cors(handler)
        handler.end_headers()
        handler.wfile.write(raw)
        return True

    if path in ("/download/apk", "/GoldenShield-Control.apk", "/app.apk"):
        apk = Path(r"C:\Users\Public\GoldenShield-Control.apk")
        if not apk.exists():
            apk = ROOT / "downloads" / "GoldenShield-Control.apk"
        if not apk.exists():
            send_json(handler, 404, {"ok": False, "error": "apk not found"})
            return True
        raw = apk.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/vnd.android.package-archive")
        handler.send_header(
            "Content-Disposition",
            "attachment; filename=GoldenShield-Control.apk",
        )
        handler.send_header("Content-Length", str(len(raw)))
        send_cors(handler)
        handler.end_headers()
        handler.wfile.write(raw)
        return True

    if path in ("/download/live-base", "/LIVE_API_BASE.txt", "/api/live-base"):
        tun = bb.tunnel_url().lstrip("\ufeff").strip().rstrip("/")
        if not tun.startswith("http"):
            host = (handler.headers.get("Host") or "").strip()
            if host and "trycloudflare.com" in host:
                tun = f"https://{host.split(':')[0]}"
        if not tun.startswith("http"):
            send_json(handler, 503, {"ok": False, "error": "tunnel url unavailable"})
            return True
        raw = (tun + "\n").encode("utf-8")
        try:
            (RUNTIME / "mobile_tunnel_url.txt").write_text(tun + "\n", encoding="utf-8")
        except Exception:
            pass
        handler.send_response(200)
        handler.send_header("Content-Type", "text/plain; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", str(len(raw)))
        send_cors(handler)
        handler.end_headers()
        handler.wfile.write(raw)
        return True
    return False
