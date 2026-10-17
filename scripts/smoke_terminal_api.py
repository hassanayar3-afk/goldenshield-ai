#!/usr/bin/env python3
"""Smoke test — GoldenShield Terminal API (محلي أو VPS)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.getenv("SMOKE_MOBILE_API_PORT", os.getenv("MOBILE_API_PORT", "18790")) or 18790)
BASE = f"http://127.0.0.1:{PORT}"


def _get(path: str, token: str | None = None) -> dict:
    req = urllib.request.Request(BASE + path)
    if token:
        req.add_header("X-GS-Token", token)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(path: str, body: dict, token: str | None = None) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-GS-Token", token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    os.chdir(ROOT)
    os.environ.setdefault("GOLDENSHIELD_OFFICIAL_ROOT", str(ROOT))
    env = os.environ.copy()
    env["GOLDENSHIELD_OFFICIAL_ROOT"] = str(ROOT)
    env["MOBILE_API_PORT"] = str(PORT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "terminal_app.server"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(2.5)
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                health = _get("/api/health")
                if health.get("ok"):
                    break
            except (urllib.error.URLError, TimeoutError, urllib.error.HTTPError):
                time.sleep(0.5)
        else:
            print("SMOKE_FAIL: health timeout")
            return 1

        boot = _get("/api/bootstrap")
        assert boot.get("ok"), boot
        pair_code = boot.get("pair_code") or ""
        assert pair_code, "missing pair_code in bootstrap"

        paired = _post("/api/pair", {"pair_code": pair_code, "device_name": "SmokeTest"})
        token = paired.get("device_token")
        assert token, paired

        status = _get("/api/status", token)
        assert status.get("ok"), status

        stack = _get("/api/stack", token)
        assert stack.get("ok"), stack

        ws_snap = _get("/api/ws/snapshot", token)
        assert ws_snap.get("ok"), ws_snap

        panel = urllib.request.urlopen(BASE + "/", timeout=10)
        assert panel.status == 200

        print("SMOKE_OK: health bootstrap pair status stack ws panel")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
