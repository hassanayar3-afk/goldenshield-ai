"""تشخيص وإقلاع البوت رغم المسافات في المسار."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

HOST = os.environ["WIN_HOST"]
USER = os.environ["WIN_USER"]
PASSWORD = os.environ["WIN_PASSWORD"]
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
BOT = r"C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227"
ALT = r"C:\GoldenShield"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    safe = text[:4500].encode("ascii", errors="replace").decode("ascii")
    print(f"[{code}] {safe}\n")
    return text


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)

    # اقرأ آخر السجلات
    for bot in (BOT, ALT):
        run(
            ssh,
            "powershell -NoProfile -Command "
            f"\"Write-Output '=== {bot} ==='; "
            f"Test-Path '{bot}\\main.py'; "
            f"if (Test-Path '{bot}\\storage\\logs\\stdout.log') {{ Get-Content '{bot}\\storage\\logs\\stdout.log' -Tail 30 }}; "
            f"if (Test-Path '{bot}\\storage\\logs\\errors.log') {{ Write-Output '--- errors ---'; Get-Content '{bot}\\storage\\logs\\errors.log' -Tail 20 }}\"",
        )

    # اختبار إقلاع سريع لمعرفة الخطأ (15 ثانية)
    print("PROBE_IMPORT")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Set-Location '{BOT}'; & '{PY}' -c \\\"print('pyok'); from config.settings import load_settings; s=load_settings(reload=True); print(s.execution_mode, s.execution_backend, s.binance_demo_trading, s.mt5_enabled)\\\"\"",
        timeout=60,
    )

    # أنشئ junction بدون مسافات لتسهيل التشغيل
    junction = r"C:\GSBot"
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"if (Test-Path '{junction}') {{ cmd /c rmdir '{junction}' }}; "
        f"cmd /c mklink /J '{junction}' '{BOT}'\"",
    )

    # أوقف القديم
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{junction}\\storage\\runtime\\user_stopped.flag' -EA SilentlyContinue; "
        f"New-Item -ItemType Directory -Force -Path '{junction}\\storage\\logs' | Out-Null\"",
    )

    # مهمة مجدولة على المسار القصير
    run(ssh, "schtasks /Delete /TN GoldenShieldBotVisible /F")
    create = (
        "powershell -NoProfile -Command "
        "\"$tr='cmd.exe /c cd /d C:\\GSBot && "
        f"\\\"{PY}\\\" -u main.py >> storage\\logs\\bot_stdout.log 2>&1'; "
        "schtasks /Create /TN GoldenShieldBotVisible /TR $tr /SC ONCE /ST 00:00 /RL HIGHEST /F; "
        "schtasks /Run /TN GoldenShieldBotVisible; "
        "schtasks /Query /TN GoldenShieldBotVisible /V /FO LIST | Select-String 'Task To Run|Status|Last Run'\""
    )
    run(ssh, create)
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
        "\"if (Test-Path 'C:\\GSBot\\storage\\logs\\bot_stdout.log') { Get-Content 'C:\\GSBot\\storage\\logs\\bot_stdout.log' -Tail 40 } "
        "elseif (Test-Path 'C:\\GSBot\\storage\\logs\\stdout.log') { Get-Content 'C:\\GSBot\\storage\\logs\\stdout.log' -Tail 40 } "
        "else { 'NO_LOG' }\"",
    )

    # fallback Start-Process من C:\GSBot
    if "ProcessId" not in proc:
        print("FALLBACK")
        run(
            ssh,
            "powershell -NoProfile -Command "
            f"\"Start-Process -FilePath '{PY}' -ArgumentList '-u','main.py' -WorkingDirectory 'C:\\GSBot' -WindowStyle Minimized\"",
        )
        time.sleep(10)
        proc = run(
            ssh,
            "powershell -NoProfile -Command "
            "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
            "Select-Object ProcessId,CommandLine | Format-List\"",
        )
        run(
            ssh,
            "powershell -NoProfile -Command "
            "\"Get-Content 'C:\\GSBot\\storage\\logs\\stdout.log' -Tail 50 -EA SilentlyContinue; "
            "Get-Content 'C:\\GSBot\\storage\\logs\\errors.log' -Tail 30 -EA SilentlyContinue\"",
        )

    ssh.close()
    ok = "ProcessId" in proc
    print("BOT_RUNNING" if ok else "BOT_NOT_RUNNING")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
