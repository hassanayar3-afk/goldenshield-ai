"""تشغيل البوت على Windows VPS الآن."""

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
CANDIDATES = [
    r"C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227",
    r"C:\GoldenShield",
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[int, str]:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    print(f"[{code}] {text[:3000]}\n")
    return code, text


def main() -> int:
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

    find_ps = (
        "powershell -NoProfile -Command "
        "\"$c=@('C:\\Users\\Administrator\\Downloads\\Telegram Desktop\\GoldenShield_CONTABO_DEMO_20260728_2227',"
        "'C:\\GoldenShield'); "
        "foreach($p in $c){ if(Test-Path (Join-Path $p 'main.py')){ Write-Output $p } }\""
    )
    _, listing = run(ssh, find_ps)
    roots = [ln.strip() for ln in listing.splitlines() if ln.strip().lower().startswith("c:")]
    if not roots:
        print("NO_ROOT")
        return 1
    root = roots[0]
    for r in roots:
        if "CONTABO" in r.upper() or "DEMO" in r.upper():
            root = r
            break
    print("ROOT=", root)

    flag = str(Path(root) / "storage" / "runtime" / "user_stopped.flag")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{flag}' -EA SilentlyContinue; "
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; "
        "Start-Sleep -Seconds 2\"",
    )

    # رقّع .env Demo
    ps1 = root + "\\_boot_env.ps1"
    script = r"""
param([string]$Root)
$p = Join-Path $Root '.env'
$demo = Join-Path $Root '.env.demo'
if (-not (Test-Path $p) -and (Test-Path $demo)) { Copy-Item $demo $p }
if (-not (Test-Path $p)) { Write-Output 'NO_ENV'; exit 1 }
$map = @{
  'EXECUTION_MODE' = 'live'
  'EXECUTION_BACKEND' = 'binance'
  'BINANCE_DEMO_TRADING' = 'true'
  'MT5_ENABLED' = 'false'
  'BOT_AUTO_SYNC_MT5' = 'false'
  'TELEGRAM_SIGNALS_ONLY' = 'false'
}
$drop = @('MT5_LOGIN','MT5_PASSWORD','MT5_SERVER','MT5_BROKER','MT5_TERMINAL_PATH')
$lines = Get-Content $p
$seen = @{}
$out = foreach ($line in $lines) {
  if ($line -match '^\s*#') { $line; continue }
  if ($line -notmatch '=') { $line; continue }
  $k = ($line.Split('=',2)[0]).Trim()
  if ($drop -contains $k) { continue }
  if ($map.ContainsKey($k)) { $seen[$k] = $true; "$k=$($map[$k])"; continue }
  $line
}
foreach ($k in $map.Keys) {
  if (-not $seen.ContainsKey($k)) { $out += "$k=$($map[$k])" }
}
Set-Content -Path $p -Value $out -Encoding UTF8
Write-Output 'ENV_OK'
Get-Content $p | Where-Object { $_ -match '^(EXECUTION_|BINANCE_DEMO|MT5_ENABLED|BOT_AUTO|TELEGRAM_SIGNALS)=' }
"""
    sftp = ssh.open_sftp()
    with sftp.file(ps1.replace("\\", "/"), "w") as f:
        f.write(script)
    sftp.close()
    run(ssh, f'powershell -NoProfile -ExecutionPolicy Bypass -File "{ps1}" -Root "{root}"')

    # تشغيل
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"$py='{PY}'; if (-not (Test-Path $py)) {{ $py='py' }}; "
        f"Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory '{root}' "
        "-WindowStyle Minimized\"",
    )
    time.sleep(8)

    _, proc = run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"$py='{PY}'; if (-not (Test-Path $py)) {{ $py='py' }}; "
        f"Set-Location '{root}'; "
        "& $py -c \\\"from config.settings import load_settings; s=load_settings(reload=True); "
        "print('mt5', s.mt5_enabled); print('mode', s.execution_mode); "
        "print('backend', s.execution_backend); print('demo', s.binance_demo_trading)\\\"\"",
    )

    ssh.close()
    if "ProcessId" not in proc and "main.py" not in proc.lower():
        print("START_FAILED")
        return 1
    print("BOT_RUNNING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
