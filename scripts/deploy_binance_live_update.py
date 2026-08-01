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
    "config/mt5_symbol_map.yaml",
    "config/trading_pairs.yaml",
    "operations/telegram_dashboard.py",
    "operations/telegram_keyboards.py",
    "operations/telegram_commands.py",
    "operations/telegram_admin.py",
    "operations/bot_admin.py",
    "operations/message_templates.py",
    "operations/dashboard_templates.py",
    "risk/iron_protocol.py",
    "execution/mt5_bridge.py",
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
    # سطر واحد PowerShell لتجنب مشاكل الاقتباس
    cmd = (
        "powershell -NoProfile -Command "
        "\"$c=@(); "
        "if(Test-Path 'C:\\GoldenShield\\main.py'){$c+='C:\\GoldenShield'}; "
        "Get-ChildItem 'C:\\Users\\Administrator\\Downloads\\Telegram Desktop' -Directory -EA SilentlyContinue | "
        "ForEach-Object { if(Test-Path (Join-Path $_.FullName 'main.py')){ $c+=$_.FullName } }; "
        "Get-ChildItem 'C:\\Users\\Administrator\\Downloads' -Directory -EA SilentlyContinue | "
        "ForEach-Object { if(Test-Path (Join-Path $_.FullName 'main.py')){ $c+=$_.FullName } }; "
        "($c | Select-Object -First 1)\""
    )
    _, text = run(ssh, cmd)
    for line in text.splitlines():
        line = line.strip().strip('"')
        if line.lower().startswith("c:") and "main.py" not in line.lower():
            return line
    # بحث أوسع
    cmd2 = (
        "powershell -NoProfile -Command "
        "\"Get-ChildItem -Path C:\\Users\\Administrator -Recurse -Filter main.py -EA SilentlyContinue | "
        "Where-Object { $_.DirectoryName -match 'GoldenShield' } | "
        "Select-Object -First 5 -ExpandProperty DirectoryName\""
    )
    _, text2 = run(ssh, cmd2, timeout=300)
    for line in text2.splitlines():
        line = line.strip()
        if line.lower().startswith("c:"):
            return line
    raise SystemExit(f"bot root not found:\n{text}\n{text2}")


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
$map['MT5_ENABLED'] = 'false'
$map['BOT_AUTO_SYNC_MT5'] = 'false'
$map['MT5_ATTACH_SL_TP'] = 'false'
$map['TELEGRAM_SIGNALS_ONLY'] = 'false'
$map['TELEGRAM_SEND_CYCLE_SIGNALS'] = 'true'
$map['TELEGRAM_LIVE_SIGNALS'] = 'true'
$map['TELEGRAM_LIVE_SIGNALS_SECONDS'] = '15'
$map['LOOP_INTERVAL_SECONDS'] = '15'
$drop = @('MT5_LOGIN','MT5_PASSWORD','MT5_SERVER','MT5_BROKER','MT5_TERMINAL_PATH')
$out = New-Object System.Collections.Generic.List[string]
foreach ($line in $lines) {
  if ($line -match '^\s*#') { $out.Add($line); continue }
  if ($line -notmatch '=') { $out.Add($line); continue }
  $k = ($line.Split('=',2)[0]).Trim()
  if ($drop -contains $k) { continue }
  if ($map.ContainsKey($k)) { $out.Add("$k=$($map[$k])"); $map.Remove($k) }
  else { $out.Add($line) }
}
foreach ($k in @('EXECUTION_MODE','EXECUTION_BACKEND','BINANCE_DEMO_TRADING','MT5_ENABLED','BOT_AUTO_SYNC_MT5','MT5_ATTACH_SL_TP','TELEGRAM_SIGNALS_ONLY','TELEGRAM_SEND_CYCLE_SIGNALS','TELEGRAM_LIVE_SIGNALS','TELEGRAM_LIVE_SIGNALS_SECONDS','LOOP_INTERVAL_SECONDS')) {
  if ($map.ContainsKey($k)) { $out.Add("$k=$($map[$k])") }
}
Set-Content -Path $envPath -Value $out -Encoding UTF8
Write-Output 'ENV_PATCHED'
Select-String -Path $envPath -Pattern '^(EXECUTION_|BINANCE_DEMO|MT5_ENABLED|BOT_AUTO|TELEGRAM_SIGNALS)' | ForEach-Object { $_.Line }
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
