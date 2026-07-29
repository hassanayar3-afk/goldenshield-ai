"""أدوات دورة حياة البوت — إيقاف/تشغيل من سطر الأوامر أو ملفات bat."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operations.shutdown_guard import clear_user_stop, is_user_stopped, request_user_stop, stop_info


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: lifecycle.py [clear-stop|request-stop|status] [reason]")
        return 1

    cmd = args[0].lower()
    if cmd == "clear-stop":
        cleared = clear_user_stop()
        print("cleared" if cleared else "not_stopped")
        return 0

    if cmd == "request-stop":
        reason = args[1] if len(args) > 1 else "manual_stop"
        request_user_stop(reason, source="cli")
        print(f"stopped:{reason}")
        return 0

    if cmd == "status":
        if is_user_stopped():
            print(stop_info())
            return 0
        print("running")
        return 0

    print(f"unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
