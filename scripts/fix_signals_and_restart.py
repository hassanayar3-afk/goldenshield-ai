"""تفعيل إشارات التيليجرام وإعادة تشغيل نظيف من الحزمة الجديدة."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh, cmd, timeout=180):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    text = (o.read() + e.read()).decode("utf-8", errors="replace")
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

    # أوقف كل عمليات main.py
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; Start-Sleep -Seconds 3\"",
    )

    # رقّع .env: إشارات الدورة + تأكيد ديمو
    ps = r"""
param([string]$Root)
$p = Join-Path $Root '.env'
$map = @{
  'EXECUTION_MODE'='live'
  'EXECUTION_BACKEND'='binance'
  'BINANCE_DEMO_TRADING'='true'
  'MT5_ENABLED'='false'
  'TELEGRAM_SIGNALS_ONLY'='false'
  'TELEGRAM_SEND_CYCLE_SIGNALS'='true'
  'MANUAL_ENTRY_REQUIRED'='false'
  'AUTO_ENTRY_MIN_PERCENT'='95'
}
$lines = Get-Content $p
$seen = @{}
$out = foreach ($line in $lines) {
  if ($line -match '^([^=]+)=(.*)$') {
    $k = $Matches[1].Trim()
    if ($map.ContainsKey($k)) { $seen[$k]=$true; "$k=$($map[$k])"; continue }
  }
  $line
}
foreach ($k in $map.Keys) { if (-not $seen.ContainsKey($k)) { $out += "$k=$($map[$k])" } }
Set-Content $p $out -Encoding UTF8
Get-Content $p | Where-Object { $_ -match '^(EXECUTION_|BINANCE_DEMO|TELEGRAM_SEND|TELEGRAM_SIGNALS|AUTO_ENTRY|MANUAL_ENTRY|MT5_ENABLED)=' }
"""
    remote = KEEP + r"\_patch_signals.ps1"
    sftp = ssh.open_sftp()
    with sftp.file(remote.replace("\\", "/"), "w") as f:
        f.write(ps)
    sftp.close()
    run(ssh, f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}" -Root "{KEEP}"')

    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{KEEP}\\storage\\runtime\\user_stopped.flag' -EA SilentlyContinue\"",
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
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Set-Location '{KEEP}'; & '{PY}' -c \\\"from config.settings import load_settings; s=load_settings(reload=True); "
        "print('demo',s.binance_demo_trading,'mode',s.execution_mode,'cycle',s.telegram_send_cycle_signals,'auto',s.auto_entry_min_percent); "
        "from data.exchange_client import get_exchange, reset_exchange; reset_exchange(); b=get_exchange().fetch_balance().get('USDT') or {}; print('USDT_free', b.get('free'))\\\"\"",
    )
    ssh.close()
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
