"""JSON / CORS helpers for BaseHTTPRequestHandler."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler


def send_cors(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, X-GS-Token, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")


def send_json(handler: BaseHTTPRequestHandler, code: int, payload) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    send_cors(handler)
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))
