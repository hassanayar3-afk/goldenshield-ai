"""اختبار بسيط: هل بايثون يلتصق بـ MT5 المفتوح؟"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    dotenv = ROOT / ".env"
    if not dotenv.exists():
        return env
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def main() -> int:
    print("Python:", sys.executable)
    print("Version:", sys.version)
    print()

    if sys.version_info[:2] >= (3, 13):
        print("WARNING: use Python 3.12 for MetaTrader5")
        print()

    try:
        import MetaTrader5 as mt5
    except Exception as exc:
        print("RESULT=FAILED")
        print("ERROR: MetaTrader5 package missing")
        print(exc)
        return 1

    env = _load_env()
    terminal = env.get("MT5_TERMINAL_PATH", r"C:\Program Files\XM MT5\terminal64.exe")
    login = env.get("MT5_LOGIN", "")
    password = env.get("MT5_PASSWORD", "")
    server = env.get("MT5_SERVER", "XMGlobal-MT5 10")

    print("terminal =", terminal)
    print("login    =", login)
    print("server   =", server)
    print()

    attempts: list[tuple[str, dict]] = []

    if login and password and server:
        attempts.append(
            (
                "initialize(path+login+password+server)",
                {
                    "path": terminal,
                    "login": int(login),
                    "password": password,
                    "server": server,
                },
            )
        )

    if Path(terminal).exists():
        attempts.append(("initialize(path only)", {"path": terminal}))

    attempts.append(("initialize() attach", {}))

    ok = False
    err = None
    info = None
    for label, kwargs in attempts:
        print(f"Trying {label} ...")
        ok = mt5.initialize(**kwargs)
        err = mt5.last_error()
        info = mt5.account_info()
        print("  initialize =", ok)
        print("  error      =", err)
        print("  account    =", info)
        if ok and info is not None:
            print("  METHOD OK  =", label)
            break
        try:
            mt5.shutdown()
        except Exception:
            pass
        print()

    print()
    if ok and info is not None:
        print("RESULT=SUCCESS")
        print("login =", info.login)
        print("server =", getattr(info, "server", "?"))
        print("balance =", getattr(info, "balance", "?"))
        return 0

    print("RESULT=FAILED")
    print("error =", err)
    print()
    print("Fix:")
    print("1) MT5 open + logged in")
    print("2) Allow algo ON / Disable Python API OFF")
    print("3) Check .env MT5_PASSWORD and MT5_SERVER")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
