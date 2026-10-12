"""POST /api/act — أوامر التحكم + Pocket Lock."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from terminal_app.config import RUNTIME, STRATEGY_CODE
from terminal_app.auth.twofa_guard import verify_totp
from terminal_app.http.auth_adapter import HandlerAuthAdapter, auth_ok, pocket_lock
from terminal_app.http.json_io import send_json
from terminal_app.services import mobile_core as core


def handle_act_post(handler: BaseHTTPRequestHandler, body: dict) -> bool:
    act = str(body.get("act") or "")
    critical = {
        "panic",
        "close_all",
        "close_winners",
        "close_losers",
        "close_symbol",
        "resume",
    }
    try:
        lock = pocket_lock().evaluate_critical_action(
            act,
            body if isinstance(body, dict) else {},
            HandlerAuthAdapter(handler),
        )
        if not lock.allowed and act in critical:
            send_json(
                handler,
                403,
                {"ok": False, "error": lock.code, "reason": lock.reason},
            )
            return True
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"pocket_lock: {exc}"})
        return True

    if act == "pause":
        (RUNTIME / "user_stopped.flag").write_text("mobile-pause", encoding="utf-8")
        core._push_alert("control", "إيقاف من التطبيق", "تم طلب إيقاف الدخول", level="warn")
        send_json(handler, 200, {"ok": True, "paused": True})
        return True

    if act == "resume":
        flag = RUNTIME / "user_stopped.flag"
        if flag.exists():
            flag.unlink()
        core._push_alert("control", "تشغيل من التطبيق", "تم استئناف الدخول", level="ok")
        send_json(handler, 200, {"ok": True, "paused": False})
        return True

    if act == "refresh":
        core._parse_signals_from_log()
        core._write_heartbeat({"reason": "refresh"})
        send_json(handler, 200, {"ok": True, "status": core._status()})
        return True

    if act in {"close_all", "close_winners", "close_losers", "close_symbol"}:
        mode = {
            "close_all": "all",
            "close_winners": "winners",
            "close_losers": "losers",
            "close_symbol": "symbol",
        }[act]
        symbol = str(body.get("symbol") or body.get("sym") or "").strip() or None
        if act == "close_symbol" and not symbol:
            send_json(handler, 400, {"ok": False, "error": "symbol required", "closed": []})
            return True
        result = core._close_positions(
            mode,
            symbol=symbol if act == "close_symbol" else None,
        )
        core._push_alert(
            "control",
            "إغلاق من التطبيق",
            result.get("message") or act,
            level="trade" if result.get("closed") else "info",
        )
        send_json(handler, 200 if result.get("ok") else 500, result)
        return True

    totp_code = str(body.get("totp") or body.get("otp") or "").strip()
    twofa = verify_totp(totp_code)
    if act in critical and not twofa.ok and twofa.reason not in {"2fa_disabled"}:
        send_json(handler, 403, {"ok": False, "error": twofa.reason})
        return True

    if act == "panic":
        result = core._close_positions("all")
        (RUNTIME / "user_stopped.flag").write_text("mobile-panic", encoding="utf-8")
        (RUNTIME / "panic_touch_lock.flag").write_text("latched", encoding="utf-8")
        core._push_alert(
            "control",
            "طوارئ من التطبيق",
            result.get("message") or "panic",
            level="emergency",
        )
        result["paused"] = True
        result["panic"] = True
        send_json(handler, 200 if result.get("ok") else 500, result)
        return True

    send_json(handler, 400, {"ok": False, "error": f"unknown act {act}"})
    return True


def handle_heartbeat_post(handler: BaseHTTPRequestHandler, body: dict) -> bool:
    if not auth_ok(handler):
        send_json(handler, 401, {"ok": False, "error": "unauthorized"})
        return True
    token = handler.headers.get("X-GS-Token") or ""
    data = core._devices()
    if token in data.get("devices", {}):
        data["devices"][token]["last_seen"] = core._utc()
        core._save_devices(data)
    since = str(body.get("since") or "")
    items = core._alerts()
    if since:
        items = [alert for alert in items if str(alert.get("ts", "")) > since]
    send_json(
        handler,
        200,
        {
            "ok": True,
            "status": core._status(),
            "alerts": items[-30:],
            "rules": core._rules_payload(),
            "discord": core._discord_cfg_public(),
            "strategy_code": STRATEGY_CODE,
        },
    )
    return True
