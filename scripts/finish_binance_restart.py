"""إعادة تشغيل البوت على المسار الرسمي فقط: C:\\GoldenShield_Binance."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from scripts.vps_official import OFFICIAL_ROOT_STR, assert_official_only  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

HOST = os.environ["WIN_HOST"]
USER = os.environ["WIN_USER"]
PASSWORD = os.environ["WIN_PASSWORD"]
REMOTE = assert_official_only("finish_binance_restart")
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[int, str]:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    print(f"[{code}] {text[:3000]}\n")
    return code, text


def main() -> int:
    root = REMOTE
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    print("USING_ROOT=", root)

    files = [
        "core/constants.py",
        "config/runtime_profile.py",
        "config/settings.py",
        "operations/telegram_dashboard.py",
        "operations/telegram_keyboards.py",
        "operations/telegram_commands.py",
        "operations/telegram_admin.py",
        "operations/message_templates.py",
        "operations/single_instance.py",
    ]
    sftp = ssh.open_sftp()
    for rel in files:
        local = ROOT / rel
        if not local.is_file():
            continue
        remote = str(Path(root) / Path(rel)).replace("\\", "/")
        remote_dir = str(Path(root) / Path(rel).parent).replace("/", "\\")
        run(
            ssh,
            "powershell -NoProfile -Command "
            f"\"New-Item -ItemType Directory -Force -Path '{remote_dir}' | Out-Null\"",
        )
        sftp.put(str(local), remote)
        print("PUT", rel)
    sftp.close()

    flag = str(Path(root) / "storage" / "runtime" / "user_stopped.flag")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{flag}' -EA SilentlyContinue; "
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; "
        "Start-Sleep -Seconds 2\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"$py='{PY}'; if(-not (Test-Path $py)){{ $py='py' }}; "
        f"Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory '{root}' "
        "-WindowStyle Minimized; Start-Sleep -Seconds 8; "
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\\.py' } | "
        "Measure-Object | Select-Object -ExpandProperty Count\"",
    )
    ssh.close()
    print("ALL_DONE", OFFICIAL_ROOT_STR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
