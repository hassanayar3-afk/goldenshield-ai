"""تشغيل قوي للبوت عبر مهمة مجدولة + فحص السجل."""

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


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    print(f"[{code}] {text[:3500]}\n")
    return text


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)

    # تأكد من وجود المجلد
    exists = run(ssh, f'powershell -NoProfile -Command "Test-Path \'{BOT}\\main.py\'"')
    if "True" not in exists:
        alt = r"C:\GoldenShield"
        exists2 = run(ssh, f'powershell -NoProfile -Command "Test-Path \'{alt}\\main.py\'"')
        bot = alt if "True" in exists2 else BOT
    else:
        bot = BOT
    print("BOT_DIR=", bot)

    run(ssh, f'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path \'{bot}\\storage\\logs\',\'{bot}\\storage\\runtime\' | Out-Null"')
    run(ssh, f'powershell -NoProfile -Command "Remove-Item -Force \'{bot}\\storage\\runtime\\user_stopped.flag\' -EA SilentlyContinue"')

    # أوقف أي main.py سابق
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; Start-Sleep -Seconds 2\"",
    )

    # اكتب start_visible.bat
    bat = (
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        f"\"{PY}\" -u main.py >> storage\\logs\\bot_stdout.log 2>&1\r\n"
    )
    sftp = ssh.open_sftp()
    with sftp.file((bot + "\\start_visible.bat").replace("\\", "/"), "w") as f:
        f.write(bat)
    sftp.close()

    # مهمة مجدولة
    run(ssh, "schtasks /Delete /TN GoldenShieldBotVisible /F")
    # استخدم cmd /c مع مسار فيه مسافات
    tr = f'cmd.exe /c "cd /d \"{bot}\" && start_visible.bat"'
    # عبر powershell Create
    create_cmd = (
        "powershell -NoProfile -Command "
        f"\"$tr='cmd.exe /c cd /d \\\"{bot}\\\" & start_visible.bat'; "
        "schtasks /Create /TN GoldenShieldBotVisible /TR $tr /SC ONCE /ST 00:00 /RL HIGHEST /F; "
        "schtasks /Run /TN GoldenShieldBotVisible\""
    )
    run(ssh, create_cmd)

    time.sleep(12)

    proc = run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )
    log_path = bot + r"\storage\logs\bot_stdout.log"
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"if (Test-Path '{log_path}') {{ Get-Content '{log_path}' -Tail 50 }} else {{ 'NO_STDOUT_LOG' }}\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Get-ChildItem '{bot}\\storage\\logs' -EA SilentlyContinue | "
        "Sort-Object LastWriteTime -Descending | Select-Object -First 8 Name,LastWriteTime,Length | Format-Table -AutoSize\"",
    )

    # إن فشلت المهمة: Start-Process مباشر مع Redirect
    if "ProcessId" not in proc:
        print("FALLBACK_START_PROCESS")
        run(
            ssh,
            "powershell -NoProfile -Command "
            f"\"$log='{bot}\\storage\\logs\\bot_stdout.log'; "
            f"Start-Process -FilePath '{PY}' -ArgumentList '-u','main.py' -WorkingDirectory '{bot}' "
            "-RedirectStandardOutput $log -RedirectStandardError ($log+'.err') -WindowStyle Hidden\"",
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
            f"\"Get-Content '{log_path}' -Tail 60 -EA SilentlyContinue; "
            f"Get-Content '{log_path}.err' -Tail 60 -EA SilentlyContinue\"",
        )

    ssh.close()
    ok = "ProcessId" in proc
    print("BOT_RUNNING" if ok else "BOT_NOT_RUNNING")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
