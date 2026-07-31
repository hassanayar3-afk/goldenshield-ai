"""إيقاف النسخ المتعارضة وتشغيل GoldenShield_Binance فقط مع مهمة ثابتة."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
OLD = r"C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227"


def run(ssh, cmd, timeout=180):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    text = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(text[:3500].encode("ascii", "replace").decode("ascii"))
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

    # أوقف كل عمليات البوت
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py|00_START\\.bat|GoldenShield' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; "
        "schtasks /End /TN GoldenShieldBotVisible 2>$null; Start-Sleep -Seconds 3\"",
    )

    # عطّل مجلد القديم إن وُجد
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"$old='C:\\Users\\Administrator\\Downloads\\Telegram Desktop\\GoldenShield_CONTABO_DEMO_20260728_2227'; "
        "$dead=$old+'_DISABLED'; "
        "if (Test-Path $old) { "
        "  if (Test-Path $dead) { Remove-Item -LiteralPath $dead -Recurse -Force -EA SilentlyContinue }; "
        "  Rename-Item -LiteralPath $old -NewName 'GoldenShield_CONTABO_DEMO_20260728_2227_DISABLED' -Force; "
        "  'OLD_DISABLED' "
        "} else { 'OLD_ALREADY_GONE' }\"",
    )

    # امسح stop flag وطابق junction
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{KEEP}\\storage\\runtime\\user_stopped.flag' -EA SilentlyContinue; "
        f"if (Test-Path 'C:\\GSBot') {{ cmd /c rmdir C:\\GSBot }}; cmd /c mklink /J C:\\GSBot '{KEEP}'\"",
    )

    # مهمة تعمل عند تسجيل الدخول + عند البدء (أفضل من ONCE)
    run(ssh, "schtasks /Delete /TN GoldenShieldBotVisible /F")
    run(ssh, "schtasks /Delete /TN GoldenShieldBotBoot /F")

    # إنشاء مهمة عند بدء التشغيل تعمل سواء كانت جلسة تفاعلية أم لا قدر الإمكان
    create = (
        "powershell -NoProfile -Command "
        f"\"$tr='cmd.exe /c cd /d {KEEP} && \\\"{PY}\\\" -u main.py >> storage\\logs\\bot_stdout.log 2>&1'; "
        "schtasks /Create /TN GoldenShieldBotBoot /TR $tr /SC ONSTART /RU SYSTEM /RL HIGHEST /F; "
        "schtasks /Create /TN GoldenShieldBotVisible /TR $tr /SC ONLOGON /RL HIGHEST /F; "
        "schtasks /Run /TN GoldenShieldBotVisible\""
    )
    run(ssh, create)

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
        f"\"Set-Location '{KEEP}'; & '{PY}' -c \\\"from config.settings import load_settings; from data.exchange_client import get_exchange,reset_exchange; "
        "s=load_settings(reload=True); reset_exchange(); b=get_exchange().fetch_balance().get('USDT') or {}; "
        "print('demo',s.binance_demo_trading,'mode',s.execution_mode,'USDT',b.get('free'))\\\"\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Write-Output ('OLD_EXISTS='+(Test-Path 'C:\\Users\\Administrator\\Downloads\\Telegram Desktop\\GoldenShield_CONTABO_DEMO_20260728_2227')); "
        "Write-Output ('OLD_DISABLED='+(Test-Path 'C:\\Users\\Administrator\\Downloads\\Telegram Desktop\\GoldenShield_CONTABO_DEMO_20260728_2227_DISABLED')); "
        "Write-Output ('NEW='+(Test-Path 'C:\\GoldenShield_Binance\\main.py'))\"",
    )

    ssh.close()
    print("STABLE_START_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
