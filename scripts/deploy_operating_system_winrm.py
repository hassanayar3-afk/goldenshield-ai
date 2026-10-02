"""نشر نظام تشغيل GoldenShield (START/STOP + no-sleep) عبر WinRM."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deploy_visible_winrm import REMOTE, _session, _upload_file  # noqa: E402

UPLOAD = [
    "GS_START.bat",
    "GS_STOP.bat",
    "START_BOT.bat",
    "STOP_BOT.bat",
    "gs_daemon.ps1",
    "run_bot_visible.cmd",
    "live_console.ps1",
    "scripts/gs_common_env.cmd",
    "scripts/gs_kill_all.ps1",
]


def main() -> int:
    session = _session()
    probe = session.run_cmd("hostname")
    if probe.status_code != 0:
        print("WINRM probe failed")
        return 1
    print("HOST", probe.std_out.decode().strip())

    for rel in UPLOAD:
        local = ROOT / rel
        if not local.is_file():
            print("SKIP", rel)
            continue
        remote = REMOTE + "\\" + rel.replace("/", "\\")
        _upload_file(session, local, remote)
        print("UP", rel)

    ps_local = ROOT / "storage" / "runtime" / "install_operating_system.ps1"
    remote_ps = r"C:\Users\Public\gs_install_operating_system.ps1"
    _upload_file(session, ps_local, remote_ps)
    print("UP install_operating_system.ps1")

    r = session.run_cmd(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"'
    )
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[-2000:].encode("ascii", "replace").decode("ascii"))
    return 0 if r.status_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
