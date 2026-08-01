"""تحقق حالة التشغيل/الإيقاف وعتبة الدخول وإرسال الإشارات."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh, cmd, timeout=120):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    text = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(text[-3500:].encode("ascii", "replace").decode("ascii"))
    return text


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    code = r'''
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from config.settings import load_settings
from core.constants import score_to_percent, is_auto_entry_allowed

s = load_settings(reload=True)
print("send_cycle_signals", getattr(s, "telegram_send_cycle_signals", None))
print("signals_only", getattr(s, "telegram_signals_only", None))
print("paused_files", list(Path("storage/runtime").glob("*")) if Path("storage/runtime").exists() else [])
for score in (8, 9, 10):
    ok, reason = is_auto_entry_allowed(score, 0)
    print("score", score, "percent", score_to_percent(score), "auto", ok, reason)
'''
    remote = KEEP + r"\_diag3.py"
    sftp = ssh.open_sftp()
    with sftp.file(remote.replace("\\", "/"), "w") as f:
        f.write(code)
    sftp.close()
    run(ssh, f'powershell -NoProfile -Command "Set-Location \'{KEEP}\'; & \'{PY}\' _diag3.py"')
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Select-String -Path '{KEEP}\\storage\\logs\\*.log' -Pattern 'Insufficient|create_order|AUTO|entry|OPEN|Order' |"
        " Select-Object -Last 40 | ForEach-Object { $_.Line }\"",
    )
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
