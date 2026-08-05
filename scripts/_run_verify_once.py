"""One-shot remote verify."""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

from scripts.verify_enterprise_remote import REMOTE_PY  # noqa: E402


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.getenv("WIN_HOST", "").strip(),
        username=os.getenv("WIN_USER", "").strip(),
        password=os.getenv("WIN_PASSWORD", ""),
        timeout=45,
    )
    sftp = client.open_sftp()
    remote = r"C:\GoldenShield_Binance\storage\runtime\_verify_enterprise.py"
    sftp.putfo(io.BytesIO(REMOTE_PY.encode("utf-8")), remote)
    sftp.close()

    cmd = (
        r'cmd /c "cd /d C:\GoldenShield_Binance && '
        r"set PYTHONPATH=C:\GoldenShield_Binance && "
        r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe "
        r'storage\runtime\_verify_enterprise.py"'
    )
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[-2000:])
    print("VERIFY_EXIT", code)

    cmd2 = (
        "powershell -NoProfile -Command "
        "\"@(Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -match 'main\\.py' }).Count\""
    )
    _stdin, stdout, stderr = client.exec_command(cmd2, timeout=60)
    mains = stdout.read().decode("utf-8", errors="replace").strip()
    print("MAIN=" + mains)
    if code == 0 and mains.isdigit() and int(mains) >= 1:
        print("FULL_AUDIT_OK")
    elif code == 0:
        print("FULL_AUDIT_WARN_NO_MAIN")
        # try start
        client.exec_command(
            r'cmd /c "schtasks /Run /TN GoldenShieldBotOfficial"',
            timeout=30,
        )
    client.close()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
