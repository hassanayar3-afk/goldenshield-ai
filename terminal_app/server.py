"""تشغيل GoldenShield Terminal Mobile API."""

from __future__ import annotations

import os
import sys
from http.server import ThreadingHTTPServer

from terminal_app.config import PAIR_CODE, PORT, RUNTIME, bootstrap
from terminal_app.http.handler import GoldenShieldRequestHandler
from terminal_app.services import mobile_core as core
from terminal_app.services.watch_log import start_watch_log_thread
from terminal_app.ws.stream_manager import get_stream_manager


def main() -> None:
    bootstrap()
    try:
        core._push_alert(
            "boot",
            "Mobile API جاهز",
            f"المنفذ {PORT} · اربط الجهاز برمز {PAIR_CODE}",
            level="ok",
        )
    except Exception as exc:
        print(f"BOOT_ALERT_FAIL:{exc}", file=sys.stderr)
    try:
        (RUNTIME / "mobile_api.pid").write_text(str(os.getpid()), encoding="ascii")
    except Exception as exc:
        print(f"PID_WRITE_FAIL:{exc}", file=sys.stderr)
    try:
        data = core._prune_devices(core._devices(), max_devices=8)
        core._save_devices(data)
    except Exception as exc:
        print(f"DEVICE_PRUNE_FAIL:{exc}", file=sys.stderr)

    start_watch_log_thread()
    manager = get_stream_manager()
    for symbol in ("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"):
        try:
            manager.ensure_binance_stream(symbol)
        except Exception:
            pass

    ThreadingHTTPServer.allow_reuse_address = True
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", PORT), GoldenShieldRequestHandler)
    except OSError as exc:
        print(f"MOBILE_API_BIND_FAIL:{PORT}:{exc}", file=sys.stderr)
        raise SystemExit(75) from exc

    from terminal_app.config import MASTER_TOKEN

    print(f"MOBILE_API_LISTENING:{PORT}", flush=True)
    print(f"MOBILE_PAIR_CODE:{PAIR_CODE}", flush=True)
    print(f"MOBILE_API_TOKEN:{MASTER_TOKEN}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("MOBILE_API_STOP", flush=True)


if __name__ == "__main__":
    main()
