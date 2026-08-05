"""إنهاء: تشغيل الحزمة الجديدة بعد حذف القديمة."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    text = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
    print(text[:3000].encode("ascii", "replace").decode("ascii"))
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

    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{KEEP}\\storage\\runtime\\user_stopped.flag' -EA SilentlyContinue; "
        f"if (-not (Test-Path 'C:\\GSBot\\main.py')) {{ if (Test-Path 'C:\\GSBot') {{ cmd /c rmdir C:\\GSBot }}; "
        f"cmd /c mklink /J C:\\GSBot '{KEEP}' }}\"",
    )
    run(ssh, "schtasks /Delete /TN GoldenShieldBotVisible /F")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"$tr='cmd.exe /c cd /d {KEEP} && \\\"{PY}\\\" -u main.py >> storage\\logs\\bot_stdout.log 2>&1'; "
        "schtasks /Create /TN GoldenShieldBotVisible /TR $tr /SC ONCE /ST 00:00 /RL HIGHEST /F; "
        "schtasks /Run /TN GoldenShieldBotVisible\"",
    )
    time.sleep(12)
    proc = run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Write-Output ('OLD_CONTABO=' + (Test-Path 'C:\\Users\\Administrator\\Downloads\\Telegram Desktop\\GoldenShield_CONTABO_DEMO_20260728_2227')); "
        "Write-Output ('OLD_GOLDEN=' + (Test-Path 'C:\\GoldenShield')); "
        "Write-Output ('NEW=' + (Test-Path 'C:\\GoldenShield_Binance\\main.py'))\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Set-Location '{KEEP}'; & '{PY}' -c \\\"from config.settings import load_settings; "
        "s=load_settings(reload=True); print(s.execution_mode, s.execution_backend, s.binance_demo_trading)\\\"\"",
    )
    ssh.close()
    print("BOT_OK" if "ProcessId" in proc else "BOT_FAIL")
    return 0 if "ProcessId" in proc else 1


if __name__ == "__main__":
    raise SystemExit(main())
