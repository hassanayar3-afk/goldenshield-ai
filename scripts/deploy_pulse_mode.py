"""نشر وضع النبض السريع (3–5s) + No-Sleep على VPS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"

UPLOADS = [
    "main.py",
    "operations/console_pulse.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_commands.py",
    "config/project_rules.py",
    "config/settings.py",
    "config/environments/production.yaml",
    "run_official_bot.ps1",
    "run_official_bot.bat",
    "START_BOT.bat",
    "REST_BOT.bat",
    "STOP_BOT.bat",
    "BOT_WINDOW.bat",
    "BOT_WINDOW.ps1",
    "00_LIVE_CONSOLE.bat",
]

ENV_MAP = {
    "NO_SLEEP_MODE": "true",
    "LOOP_INTERVAL_SECONDS": "4",
    "TELEGRAM_LIVE_SIGNALS": "true",
    "TELEGRAM_LIVE_SIGNALS_SECONDS": "4",
    "TELEGRAM_LIVE_POSITIONS_SECONDS": "3",
    "BOT_FORCE_ACTIVE": "true",
}

VERIFY = r'''
import os, sys
os.chdir(r"C:\GoldenShield_Binance")
sys.path.insert(0, r"C:\GoldenShield_Binance")
fails=[]
def ok(n,c,d=""):
    print(("PASS " if c else "FAIL ")+n+((" "+d) if d else ""))
    if not c: fails.append(n)

from operations.console_pulse import effective_loop_seconds, no_sleep_mode_enabled
ok("NO_SLEEP", no_sleep_mode_enabled())
ok("LOOP_3_5", 3 <= effective_loop_seconds(4) <= 5)

m=open("main.py",encoding="utf-8",errors="replace").read()
ok("MAIN_PULSE", "print_cycle_pulse_header" in m and "_loop_sleep_seconds" in m)

env=open(".env",encoding="utf-8",errors="replace").read().replace(" ","").lower()
ok("ENV_LOOP4", "loop_interval_seconds=4" in env)
ok("ENV_NOSLEEP", "no_sleep_mode=true" in env or "no_sleep_mode=1" in env)

print("FAILS", len(fails))
if fails:
    print("FAILED", ",".join(fails)); raise SystemExit(1)
print("PULSE_MODE_DEPLOY_OK")
'''


def main() -> int:
    host = os.getenv("WIN_HOST", "").strip()
    user = os.getenv("WIN_USER", "").strip()
    password = os.getenv("WIN_PASSWORD", "")
    if not host or not user:
        print("Missing WIN_HOST/WIN_USER", file=sys.stderr)
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45)

    sftp = client.open_sftp()
    for rel in UPLOADS:
        local = ROOT / rel
        if not local.is_file():
            print("SKIP", rel)
            continue
        remote = f"{KEEP}\\{rel.replace('/', chr(92))}"
        parent = str(Path(remote).parent)
        try:
            sftp.stat(parent)
        except OSError:
            pass
        sftp.put(str(local), remote)
        print("UPLOADED", rel)

    env_path = f"{KEEP}\\.env"
    with sftp.open(env_path, "r") as f:
        raw = f.read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    seen: set[str] = set()
    out_lines: list[str] = []
    for line in lines:
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            out_lines.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in ENV_MAP:
            out_lines.append(f"{k}={ENV_MAP[k]}")
            seen.add(k)
        else:
            out_lines.append(line)
    for k, v in ENV_MAP.items():
        if k not in seen:
            out_lines.append(f"{k}={v}")
    if not any(l.strip().upper().startswith("NO_SLEEP_MODE=") for l in out_lines):
        out_lines.append("NO_SLEEP_MODE=true")
    with sftp.open(env_path, "w") as f:
        f.write(("\n".join(out_lines) + "\n").encode("utf-8"))
    print("ENV_PULSE_SYNCED")

    sftp.put(str(ROOT / "scripts" / "deploy_pulse_mode.py"), f"{KEEP}\\storage\\runtime\\_verify_pulse.py")
    sftp.putfo(
        __import__("io").BytesIO(VERIFY.encode("utf-8")),
        f"{KEEP}\\storage\\runtime\\_verify_pulse_check.py",
    )
    sftp.close()

    cmd = (
        rf'cmd /c "cd /d {KEEP} && set PYTHONPATH={KEEP} && set NO_SLEEP_MODE=true && '
        r"set LOOP_INTERVAL_SECONDS=4 && "
        r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe "
        r'storage\runtime\_verify_pulse_check.py"'
    )
    _i, stdout, stderr = client.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[-1200:])
    print("VERIFY_EXIT", code)
    if code != 0:
        client.close()
        return code

    restart_ps = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
schtasks /End /TN 'GoldenShieldBotOfficial' /F 2>$null
Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.CommandLine -and $_.CommandLine -match 'main\.py'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep -Seconds 2
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN 'GoldenShieldBotOfficial' | Out-Null
Start-Sleep -Seconds 10
$log=Join-Path $g 'storage\logs\bot_stdout.log'
if(Test-Path $log){
  $tail=Get-Content $log -Tail 25 -Encoding UTF8 -EA SilentlyContinue
  $tail | ForEach-Object { Write-Output $_ }
}
$mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.CommandLine -match 'main\.py'
})
Write-Output ('MAIN=' + $mains.Count)
$hit=($tail -join "`n") -match 'نبض فحص السوق|LIVE SIGNALS|No-Sleep'
Write-Output ('PULSE_LOG=' + $hit)
if(($mains.Count -ge 1) -and $hit){ Write-Output 'PULSE_MODE_LIVE_OK' } else { Write-Output 'PULSE_MODE_WARN' }
Remove-Item (Join-Path $g 'storage\runtime\_verify_pulse_check.py') -Force -EA SilentlyContinue
"""
    sftp = client.open_sftp()
    with sftp.open(f"{KEEP}\\storage\\runtime\\_restart_pulse.ps1", "w") as f:
        f.write(restart_ps.encode("utf-8"))
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{KEEP}\storage\runtime\_restart_pulse.ps1"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
