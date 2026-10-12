"""GET محمية — status, account, signals, ..."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from terminal_app.http.auth_adapter import auth_ok
from terminal_app.http.json_io import send_json
from terminal_app.services import alerts_queue as aq
from terminal_app.services import binance_mirror as bm
from terminal_app.services import bot_bridge as bb


def handle_authenticated_get(handler: BaseHTTPRequestHandler, path: str) -> bool:
    if path == "/api/rules":
        if not auth_ok(handler):
            send_json(handler, 401, {"ok": False, "error": "unauthorized"})
            return True
        send_json(handler, 200, {"ok": True, "rules": bb.rules_payload()})
        return True

    if not auth_ok(handler):
        send_json(handler, 401, {"ok": False, "error": "unauthorized — pair first"})
        return True

    if path == "/api/status":
        send_json(
            handler,
            200,
            {"ok": True, "status": bb.status(), "rules": bb.rules_payload()},
        )
        return True

    if path == "/api/account":
        snap = bm.binance_snapshot(force=False)
        status = bb.status()
        if not snap.get("ok"):
            snap = bm.account_from_status(status)
            if snap.get("error") is None and status.get("exchange_error"):
                snap["error"] = status.get("exchange_error")
        send_json(
            handler,
            200,
            {
                "ok": True,
                "account": snap,
                "status": status,
                "degraded": bool(snap.get("degraded")),
            },
        )
        return True

    if path == "/api/signals":
        send_json(handler, 200, {"ok": True, "signals": bb.signals_live()})
        return True

    if path == "/api/positions":
        snap = bm.binance_snapshot()
        positions = [row for row in bb.positions() if row and not row.get("dust")]
        send_json(
            handler,
            200,
            {
                "ok": True,
                "positions": positions,
                "source": "binance" if snap.get("ok") else "bot_db",
                "equity": snap.get("equity") if snap.get("ok") else None,
            },
        )
        return True

    if path == "/api/history":
        send_json(handler, 200, {"ok": True, "history": bb.history()})
        return True

    if path == "/api/alerts":
        query = parse_qs(urlparse(handler.path).query)
        since = (query.get("since") or [""])[0]
        items = aq.alerts()
        if since:
            items = [alert for alert in items if str(alert.get("ts", "")) > since]
        send_json(handler, 200, {"ok": True, "alerts": items[-50:]})
        return True

    if path == "/api/stack":
        send_json(
            handler,
            200,
            {"ok": True, "stack": bb.stack_payload(), "status": bb.status()},
        )
        return True

    if path == "/api/battalion":
        send_json(
            handler,
            200,
            {
                "ok": True,
                "battalion": bb.battalion_payload(),
                "stack": bb.stack_payload(),
            },
        )
        return True

    if path == "/api/discord":
        send_json(
            handler,
            200,
            {
                "ok": True,
                "discord": bb.discord_cfg_public(),
                "stack": bb.stack_payload(),
            },
        )
        return True

    if path == "/api/ws/snapshot":
        from terminal_app.ws.stream_manager import get_stream_manager

        send_json(
            handler,
            200,
            {"ok": True, "events": get_stream_manager().snapshot_recent(80)},
        )
        return True

    return False
