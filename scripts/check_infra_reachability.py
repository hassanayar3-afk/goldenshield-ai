"""Quick infra check: Contabo + Windows reachability."""

from __future__ import annotations

import os
import socket

import paramiko
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"), override=True)

WIN = os.getenv("WATCHDOG_WINDOWS_HOST", "169.58.15.36")


def tcp(host: str, port: int, timeout: float = 5.0) -> str:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return "OPEN"
    except Exception as exc:
        return f"FAIL:{type(exc).__name__}"
    finally:
        s.close()


def main() -> int:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts._deploy_env import require_deploy_credentials

    contabo, user, password = require_deploy_credentials()
    print("LOCAL_TO_WIN_3389", tcp(WIN, 3389))
    print("LOCAL_TO_CONTABO_22", tcp(contabo, 22))

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        contabo,
        username=user,
        password=password,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    cmds = [
        "hostname; uptime",
        'docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | head -20',
        f"python3 - <<'PY'\nimport socket\ns=socket.socket();s.settimeout(5)\n"
        f"print('CONTABO_TO_WIN_3389', end=' ')\n"
        f"try:\n s.connect(('{WIN}',3389));print('OPEN')\n"
        f"except Exception as e:\n print(type(e).__name__)\nfinally:\n s.close()\nPY",
    ]
    for cmd in cmds:
        print(">>>", cmd.splitlines()[0][:80])
        _, stdout, stderr = client.exec_command(cmd, timeout=60)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        print(out or err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
