"""رفع بث الإشارات الحي + POL وتشغيل البوت عبر مهمة مجدولة."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"

FILES = [
    "main.py",
    "core/constants.py",
    "config/settings.py",
    "config/trading_pairs.yaml",
    "operations/dashboard_templates.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_commands.py",
    "operations/signal_filter.py",
    "risk/iron_protocol.py",
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> str:
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    text = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(text[-3500:])
    return text


def upsert_env(ssh: paramiko.SSHClient) -> None:
    remote = KEEP.replace("\\", "/") + "/_patch_live_env.py"
    code = r"""
from pathlib import Path
p = Path(r"C:\GoldenShield_Binance\.env")
text = p.read_text(encoding="utf-8", errors="replace")
updates = {
    "TELEGRAM_LIVE_SIGNALS": "true",
    "TELEGRAM_LIVE_SIGNALS_SECONDS": "15",
    "LOOP_INTERVAL_SECONDS": "15",
    "TELEGRAM_SEND_CYCLE_SIGNALS": "true",
    "AUTO_ENTRY_MIN_PERCENT": "90",
    "TELEGRAM_SIGNAL_MIN_PERCENT": "85",
}
lines = text.splitlines()
seen = set()
out = []
for line in lines:
    if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    k = line.split("=", 1)[0].strip()
    if k in updates:
        out.append(f"{k}={updates[k]}")
        seen.add(k)
    else:
        out.append(line)
for k, v in updates.items():
    if k not in seen:
        out.append(f"{k}={v}")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
for k in updates:
    print(f"{k}={updates[k]}")
"""
    sftp = ssh.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write(code)
    sftp.close()
    run(ssh, f'"{PY}" "{KEEP}\\_patch_live_env.py"')


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

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        remote = (KEEP + "\\" + rel.replace("/", "\\")).replace("\\", "/")
        print("PUT", rel)
        sftp.put(str(local), remote)

    bat = (
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        f"\"{PY}\" -u main.py >> storage\\logs\\bot_stdout.log 2>&1\r\n"
    )
    with sftp.file((KEEP + "\\start_visible.bat").replace("\\", "/"), "w") as f:
        f.write(bat)
    sftp.close()

    upsert_env(ssh)

    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
        "Start-Sleep -Seconds 2\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{KEEP}\\storage\\runtime\\user_stopped.flag' -ErrorAction SilentlyContinue; "
        f"New-Item -ItemType Directory -Force -Path '{KEEP}\\storage\\logs' | Out-Null\"",
    )

    run(ssh, "schtasks /Delete /TN GoldenShieldBotVisible /F")
    create_cmd = (
        "powershell -NoProfile -Command "
        f"\"$tr='cmd.exe /c cd /d \\\"{KEEP}\\\" & start_visible.bat'; "
        "schtasks /Create /TN GoldenShieldBotVisible /TR $tr /SC ONCE /ST 00:00 /RL HIGHEST /F; "
        "schtasks /Run /TN GoldenShieldBotVisible\""
    )
    run(ssh, create_cmd)
    time.sleep(12)

    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"if (Test-Path '{KEEP}\\storage\\logs\\bot_stdout.log') {{ "
        f"Get-Content '{KEEP}\\storage\\logs\\bot_stdout.log' -Tail 30 }} else {{ 'NO_STDOUT_LOG' }}\"",
    )
    ssh.close()
    print("FINISH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
