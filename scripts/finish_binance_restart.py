"""إعادة تشغيل بوت GoldenShield على Windows VPS والتحقق بدون طباعة أسرار."""

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
REMOTE = r"C:\GoldenShield"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
ALT_REMOTE = r"C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227"


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
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)

    # اختر المسار الذي فيه main.py ويعمل فعلياً
    _, roots = run(
        ssh,
        "powershell -NoProfile -Command "
        "\"@('C:\\GoldenShield','"
        + ALT_REMOTE.replace("\\", "\\\\")
        + "') | ForEach-Object { if(Test-Path (Join-Path $_ 'main.py')){ $_ } }\"",
    )
    candidates = [ln.strip() for ln in roots.splitlines() if ln.strip().lower().startswith("c:")]
    root = candidates[0] if candidates else REMOTE
    # فضّل مسار CONTABO إن وُجد لأنه كان المسار الحي سابقاً
    for c in candidates:
        if "CONTABO" in c.upper() or "DEMO" in c.upper():
            root = c
            break
    print("USING_ROOT=", root)

    # ارفع الملفات الحرجة مجدداً
    files = [
        "core/constants.py",
        "config/runtime_profile.py",
        "config/settings.py",
        "operations/telegram_dashboard.py",
        "operations/telegram_keyboards.py",
        "operations/telegram_commands.py",
        "operations/telegram_admin.py",
        "operations/message_templates.py",
        "execution/mt5_bridge.py",
    ]
    sftp = ssh.open_sftp()
    for rel in files:
        local = ROOT / rel
        if not local.is_file():
            continue
        remote = str(Path(root) / Path(rel)).replace("\\", "/")
        remote_dir = str(Path(root) / Path(rel).parent).replace("/", "\\")
        run(ssh, f'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path \'{remote_dir}\' | Out-Null"')
        sftp.put(str(local), remote)
        print("PUT", rel)
    sftp.close()

    # رقّع .env بدون طباعة قيم حساسة
    ps1 = root + "\\_patch_env2.ps1"
    script = r"""
param([string]$Root)
$p = Join-Path $Root '.env'
if (-not (Test-Path $p) -and (Test-Path (Join-Path $Root '.env.demo'))) { Copy-Item (Join-Path $Root '.env.demo') $p }
if (-not (Test-Path $p)) { 'NO_ENV'; exit 1 }
$wanted = @{
  'EXECUTION_MODE'='live'
  'EXECUTION_BACKEND'='binance'
  'BINANCE_DEMO_TRADING'='true'
  'MT5_ENABLED'='false'
  'BOT_AUTO_SYNC_MT5'='false'
  'MT5_ATTACH_SL_TP'='false'
  'TELEGRAM_SIGNALS_ONLY'='false'
}
$lines = Get-Content $p
$seen = @{}
$out = foreach ($line in $lines) {
  if ($line -match '^(MT5_LOGIN|MT5_PASSWORD|MT5_SERVER|MT5_BROKER|MT5_TERMINAL_PATH)=') { continue }
  if ($line -match '^([^=]+)=(.*)$') {
    $k=$Matches[1].Trim()
    if ($wanted.ContainsKey($k)) { $seen[$k]=$true; "$k=$($wanted[$k])"; continue }
  }
  $line
}
foreach ($k in $wanted.Keys) { if (-not $seen.ContainsKey($k)) { $out += "$k=$($wanted[$k])" } }
Set-Content $p $out -Encoding UTF8
'ENV_OK'
Get-Content $p | Where-Object { $_ -match '^(EXECUTION_|BINANCE_DEMO|MT5_ENABLED|BOT_AUTO|TELEGRAM_SIGNALS)=' }
"""
    sftp = ssh.open_sftp()
    with sftp.file(ps1.replace("\\", "/"), "w") as f:
        f.write(script)
    sftp.close()
    run(ssh, f'powershell -NoProfile -ExecutionPolicy Bypass -File "{ps1}" -Root "{root}"')

    # أوقف وأعد التشغيل
    flag = str(Path(root) / "storage" / "runtime" / "user_stopped.flag")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Remove-Item -Force '{flag}' -EA SilentlyContinue; "
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; "
        "Start-Sleep -Seconds 2\"",
    )

    # شغّل بالمسار الكامل لبايثون إن وُجد
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"$py='{PY}'; if(-not (Test-Path $py)){{ $py='py' }}; "
        f"Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory '{root}' "
        "-WindowStyle Minimized; Start-Sleep -Seconds 8; "
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,@{n='Cmd';e={ if($_.CommandLine.Length -gt 120){$_.CommandLine.Substring(0,120)} else {$_.CommandLine} }} | Format-List\"",
    )

    # تحقق إعدادات بدون أسرار
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"$py='{PY}'; if(-not (Test-Path $py)){{ $py='py' }}; "
        f"Set-Location '{root}'; & $py -c \\\"from config.settings import load_settings; s=load_settings(reload=True); "
        "print('mt5', s.mt5_enabled); print('mode', s.execution_mode); print('backend', s.execution_backend); "
        "print('demo', s.binance_demo_trading); print('soft_max', 5)\\\"\"",
    )

    ssh.close()
    print("ALL_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
