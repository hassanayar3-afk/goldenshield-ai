"""إيقاف عمليات main.py على ويندوز بدون PowerShell."""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import psutil  # type: ignore
    except Exception:
        print("psutil missing - use taskkill fallback from bat")
        return 2

    killed = 0
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            joined = " ".join(str(x) for x in cmd).lower()
            if "main.py" in joined and "python" in (proc.info.get("name") or "").lower():
                proc.kill()
                killed += 1
                print("killed", proc.info.get("pid"))
        except Exception:
            continue
    print("killed_count", killed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
