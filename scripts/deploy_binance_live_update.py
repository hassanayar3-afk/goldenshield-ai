"""رفع ملفات Binance-only + بث المراكز الحي إلى مسار البوت على Windows VPS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

HOST = os.environ["WIN_HOST"]
USER = os.environ["WIN_USER"]
PASSWORD = os.environ["WIN_PASSWORD"]

KEEP_ROOT = r"C:\GoldenShield_Binance"

REL_FILES = [
    "main.py",
    "core/constants.py",
    "config/runtime_profile.py",
    "config/settings.py",
    "config/trading_pairs.yaml",
    "operations/telegram_dashboard.py",
    "operations/telegram_keyboards.py",
    "operations/telegram_commands.py",
    "operations/telegram_admin.py",
    "operations/bot_admin.py",
    "operations/message_templates.py",
    "operations/dashboard_templates.py",
    "risk/iron_protocol.py",
    "scripts/windows_package.py",
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[int, str]:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    print(f"$ {cmd[:180]}...\n[{code}] {text[:2500]}\n")
    return code, text


def find_bot_root(ssh: paramiko.SSHClient) -> str:
    """المسار الرسمي فقط — لا Downloads ولا C:\\GoldenShield."""
    from scripts.vps_official import OFFICIAL_ROOT_STR, assert_official_only

    root = assert_official_only("deploy_binance_live_update")
    _, text = run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"if (Test-Path '{root}\\main.py') {{ '{root}' }} else {{ 'MISSING' }}\"",
    )
    if "MISSING" in text.upper() or root not in text:
        # ما زلنا نُلزم الرسمي إن وُجد KEEP_ROOT
        _, text2 = run(
            ssh,
            "powershell -NoProfile -Command "
            f"\"if (Test-Path '{KEEP_ROOT}\\main.py') {{ '{KEEP_ROOT}' }} else {{ 'MISSING' }}\"",
        )
        if KEEP_ROOT in text2:
            return KEEP_ROOT
        raise SystemExit(f"official bot root missing: {OFFICIAL_ROOT_STR}\n{text}\n{text2}")
    return root


def patch_env(ssh: paramiko.SSHClient, root: str) -> None:
    # اكتب سكربت مؤقت على السيرفر
    remote_ps = root.rstrip("\\") + "\\_patch_env.ps1"
    script = r"""
param([string]$Root)
$envPath = Join-Path $Root '.env'
$demo = Join-Path $Root '.env.demo'
if (-not (Test-Path $envPath) -and (Test-Path $demo)) { Copy-Item $demo $envPath }
if (-not (Test-Path $envPath)) { Write-Output 'NO_ENV'; exit 1 }
$lines = Get-Content $envPath
$map = @{}
foreach ($line in $lines) {
  if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
  $k,$v = $line.Split('=',2)
  $map[$k.Trim()] = $v
}
$map['EXECUTION_MODE'] = 'live'
$map['EXECUTION_BACKEND'] = 'binance'
$map['BINANCE_DEMO_TRADING'] = 'true'
$map['TELEGRAM_SIGNALS_ONLY'] = 'false'
$map['TELEGRAM_SEND_CYCLE_SIGNALS'] = 'true'
$map['TELEGRAM_LIVE_SIGNALS'] = 'true'
$map['TELEGRAM_LIVE_SIGNALS_SECONDS'] = '15'
$map['LOOP_INTERVAL_SECONDS'] = '15'
$out = New-Object System.Collections.Generic.List[string]
foreach ($line in $lines) {
  if ($line -match '^\s*#') { $out.Add($line); continue }
  if ($line -notmatch '=') { $out.Add($line); continue }
  $k = ($line.Split('=',2)[0]).Trim()
  if ($map.ContainsKey($k)) { $out.Add("$k=$($map[$k])"); $map.Remove($k) }
  else { $out.Add($line) }
}
foreach ($k in @('EXECUTION_MODE','EXECUTION_BACKEND','BINANCE_DEMO_TRADING','TELEGRAM_SIGNALS_ONLY','TELEGRAM_SEND_CYCLE_SIGNALS','TELEGRAM_LIVE_SIGNALS','TELEGRAM_LIVE_SIGNALS_SECONDS','LOOP_INTERVAL_SECONDS')) {
  if ($map.ContainsKey($k)) { $out.Add("$k=$($map[$k])") }
}
Set-Content -Path $envPath -Value $out -Encoding UTF8
Write-Output 'ENV_PATCHED'
Select-String -Path $envPath -Pattern '^(EXECUTION_|BINANCE_DEMO|TELEGRAM_SIGNALS)' | ForEach-Object { $_.Line }
"""
    sftp = ssh.open_sftp()
    with sftp.file(remote_ps.replace("\\", "/"), "w") as f:
        f.write(script)
    sftp.close()
    run(ssh, f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}" -Root "{root}"')


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)

    # المسار الرسمي الحالي: Binance Demo package
    _, probe = run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"if(Test-Path '{KEEP_ROOT}\\main.py'){{ '{KEEP_ROOT}' }} else {{ '' }}\"",
    )
    root = KEEP_ROOT if KEEP_ROOT.lower() in probe.lower() else find_bot_root(ssh)
    print("REMOTE_ROOT=", root)

    sftp = ssh.open_sftp()
    for rel in REL_FILES:
        local = ROOT / rel
        if not local.is_file():
            print("SKIP", rel)
            continue
        remote = str(Path(root) / Path(rel)).replace("/", "\\")
        remote_dir = str(Path(remote).parent)
        run(
            ssh,
            "powershell -NoProfile -Command "
            f"\"New-Item -ItemType Directory -Force -Path '{remote_dir}' | Out-Null\"",
        )
        print("PUT", rel)
        sftp.put(str(local), remote.replace("\\", "/"))
    sftp.close()

    patch_env(ssh, root)

    stop_flag = str(Path(root) / "storage" / "runtime" / "user_stopped.flag")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{stop_flag}' -EA SilentlyContinue; "
        "Get-Process python*,py -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue\"",
    )

    # شغّل البوت في خلفية منفصلة (مسار Python الكامل على Contabo)
    py = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Start-Process -FilePath '{py}' -ArgumentList '-u','main.py' -WorkingDirectory '{root}' "
        "-WindowStyle Minimized\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Start-Sleep -Seconds 6; "
        "Get-CimInstance Win32_Process -Filter \\\"name='python.exe' OR name='py.exe'\\\" | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )

    ssh.close()
    print("DEPLOY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
