"""POST /api/pair — ربط الجهاز."""

from __future__ import annotations

import secrets

from http.server import BaseHTTPRequestHandler

import os

from terminal_app.config import PAIR_CODE, RUNTIME, STRATEGY_CODE
from terminal_app.http.json_io import send_json
from terminal_app.services import alerts_queue as aq
from terminal_app.services import bot_bridge as bb


def web_direct_access_enabled() -> bool:
    return (os.getenv("MOBILE_WEB_DIRECT_ACCESS", "true") or "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _issue_device_token(handler: BaseHTTPRequestHandler, name: str) -> None:
    token = secrets.token_urlsafe(24)
    data = aq.devices()
    data.setdefault("devices", {})[token] = {
        "name": name,
        "paired_at": aq.utc(),
        "last_seen": aq.utc(),
        "web_direct": True,
    }
    data = aq.prune_devices(data, max_devices=8)
    aq.save_devices(data)
    tun = ""
    try:
        tun = (
            (RUNTIME / "mobile_tunnel_url.txt")
            .read_text(encoding="utf-8", errors="replace")
            .strip()
            .lstrip("\ufeff")
        )
        tun = tun.rstrip("/") if tun.startswith("https://") else ""
    except Exception:
        pass
    send_json(
        handler,
        200,
        {
            "ok": True,
            "device_token": token,
            "web_direct": True,
            "api_base_hint": tun,
            "rules": bb.rules_payload(),
            "strategy_code": STRATEGY_CODE,
            "notify_channel": "discord+mobile",
        },
    )


def handle_web_auto_pair_post(handler: BaseHTTPRequestHandler, body: dict) -> bool:
    if not web_direct_access_enabled():
        send_json(handler, 403, {"ok": False, "error": "web direct access disabled"})
        return True
    name = str(body.get("device_name") or body.get("name") or "WebPanel").strip()[:64]
    _issue_device_token(handler, name or "WebPanel")
    return True


def handle_pair_post(handler: BaseHTTPRequestHandler, body: dict) -> bool:
    code = str(body.get("pair_code") or body.get("code") or "").strip().upper()
    resume_token = str(
        body.get("device_token") or body.get("session_token") or body.get("token") or ""
    ).strip()
    name = str(body.get("device_name") or body.get("name") or "Android").strip()[:64]

    def tunnel_hint() -> str:
        try:
            tun = (
                (RUNTIME / "mobile_tunnel_url.txt")
                .read_text(encoding="utf-8", errors="replace")
                .strip()
                .lstrip("\ufeff")
            )
            return tun.rstrip("/") if tun.startswith("https://") else ""
        except Exception:
            return ""

    if resume_token:
        data = aq.devices()
        devices = data.setdefault("devices", {})
        if resume_token in devices:
            devices[resume_token]["name"] = name or devices[resume_token].get("name") or "Android"
            devices[resume_token]["last_seen"] = aq.utc()
            aq.save_devices(data)
            send_json(
                handler,
                200,
                {
                    "ok": True,
                    "resumed": True,
                    "device_token": resume_token,
                    "api_base_hint": tunnel_hint(),
                    "rules": bb.rules_payload(),
                    "strategy_code": STRATEGY_CODE,
                    "notify_channel": "discord+mobile",
                },
            )
            return True
        send_json(
            handler,
            401,
            {"ok": False, "error": "جلسة غير صالحة — أعد الربط برمز التطبيق"},
        )
        return True

    if code == STRATEGY_CODE or code in {"GS-GOLD80", "GOLD80"}:
        send_json(
            handler,
            403,
            {
                "ok": False,
                "error": "GS-GOLD80 رمز الاستراتيجية وليس رمز ربط التطبيق",
                "strategy_code": STRATEGY_CODE,
                "hint": "استخدم رمز الربط المحقون في التطبيق",
            },
        )
        return True

    if code != PAIR_CODE.upper():
        if web_direct_access_enabled() and not code:
            _issue_device_token(handler, name or "WebPanel")
            return True
        aq.push_alert("security", "محاولة ربط فاشلة", f"جهاز: {name}", level="warn")
        send_json(handler, 403, {"ok": False, "error": "رمز الربط غير صحيح"})
        return True

    _issue_device_token(handler, name or "WebPanel")
    aq.push_alert("pair", "تم ربط جهاز", f"{name} مربوط بالتطبيق", level="ok")
    return True
