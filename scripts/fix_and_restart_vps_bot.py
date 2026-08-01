"""تحديث ملفات البوت على VPS من المستودع المحلي ثم تشغيله مع لقطة إقلاع."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

REMOTE = r"C:\GoldenShield_Binance"

# ملفات/مجلدات حرجة للتحديث (بدون .env حتى لا نمسح مفاتيح السيرفر)
SYNC_PATHS = [
    "main.py",
    "intelligence",
    "risk/orderbook_imbalance_gate.py",
    "risk/risk_committee.py",
    "risk/macro_flow_gate.py",
    "execution/smart_exits.py",
    "execution/momentum_preemptive_exit.py",
    "execution/trade_executor.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_commands.py",
    "operations/message_templates.py",
    "operations/bot_admin.py",
    "operations/symbol_registry.py",
    "operations/infrastructure_watchdog.py",
    "config/settings.py",
    "config/runtime_profile.py",
    "config/risk_params.yaml",
    "database/migrations/007_shadow_stress.sql",
    "core/technical/signal_scorer.py",
    "00_START.bat",
    "00_STOP.bat",
    "00_START_KEEP_OPEN.bat",
    "00_START_VISIBLE.vbs",
    "requirements.txt",
]


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = remote_dir.replace("/", "\\").split("\\")
    cur = parts[0] + "\\" if parts[0].endswith(":") else parts[0]
    for part in parts[1:]:
        if not part:
            continue
        cur = cur.rstrip("\\") + "\\" + part
        try:
            sftp.stat(cur)
        except OSError:
            try:
                sftp.mkdir(cur)
            except OSError:
                pass


def upload_tree(sftp: paramiko.SFTPClient, local: Path, remote: str) -> int:
    n = 0
    if local.is_file():
        parent = str(Path(remote).parent).replace("/", "\\")
        sftp_mkdirs(sftp, parent)
        sftp.put(str(local), remote)
        return 1
    for path in local.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(local)
        rpath = remote.rstrip("\\") + "\\" + str(rel).replace("/", "\\")
        sftp_mkdirs(sftp, str(Path(rpath).parent))
        sftp.put(str(path), rpath)
        n += 1
    return n


def run_ps(client: paramiko.SSHClient, script: str, *, timeout: int = 180) -> str:
    remote = r"C:\Users\Public\gs_fix_run.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(script)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=timeout,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out + (("\nSTDERR:\n" + err) if err.strip() else "")


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
    if not (host and user and password):
        print("missing WIN_*")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()
    total = 0
    for rel in SYNC_PATHS:
        local = ROOT / rel
        if not local.exists():
            print("SKIP missing", rel)
            continue
        remote = REMOTE + "\\" + rel.replace("/", "\\")
        n = upload_tree(sftp, local, remote)
        total += n
        print("UP", rel, n)
    sftp.close()
    print("UPLOADED_FILES", total)

    # دمج أعلام Cognitive في .env دون لمس الأسرار
    patch = r"""
$envp = 'C:\GoldenShield_Binance\.env'
$map = @{
  'SHADOW_STRESS_ENABLED'='true'
  'SHADOW_WATCH_MINUTES'='15'
  'SHADOW_MIN_PERCENT'='90'
  'TRAP_FAIL_STREAK'='3'
  'TRAP_COOLDOWN_MINUTES'='60'
  'ORDERBOOK_IMBALANCE_GATE_ENABLED'='true'
  'ORDERBOOK_IMBALANCE_MIN'='0.15'
  'ADAPTIVE_WEIGHTS_ENABLED'='true'
  'ADAPTIVE_WEIGHT_MAX_DELTA'='0.20'
  'MOMENTUM_PREEMPTIVE_EXIT_ENABLED'='false'
  'RISK_COMMITTEE_ENABLED'='true'
  'RISK_COMMITTEE_LLM_ENABLED'='false'
  'RISK_COMMITTEE_FAIL_CLOSED'='false'
  'MACRO_FLOW_GATE_ENABLED'='true'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='1'
  'MT5_ENABLED'='false'
  'BOT_AUTO_SYNC_MT5'='false'
  'MT5_ATTACH_SL_TP'='false'
  'EXECUTION_BACKEND'='binance'
  'BINANCE_DEMO_TRADING'='true'
}
$lines = Get-Content $envp
$keys = @{}
$out = foreach ($line in $lines) {
  if ($line -match '^\s*#' -or $line -notmatch '=') { $line; continue }
  $k = ($line -split '=',2)[0].Trim()
  if ($map.ContainsKey($k)) { "$k=$($map[$k])"; $keys[$k]=1 }
  else { $line }
}
foreach ($k in $map.Keys) {
  if (-not $keys.ContainsKey($k)) { $out += "$k=$($map[$k])" }
}
# احذف أسطر بيانات MT5 الحساسة إن وُجدت
$out = $out | Where-Object { $_ -notmatch '^(MT5_LOGIN|MT5_PASSWORD|MT5_SERVER|MT5_BROKER|MT5_TERMINAL_PATH)=' }
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($envp, $out, $utf8)
Write-Host 'ENV_PATCHED'
"""
    print(run_ps(client, patch, timeout=60))

    start = r"""
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
# أوقف أي main.py قديم
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
# امسح علامة الإيقاف
$flag = Join-Path $bot 'storage\runtime\user_stopped.flag'
if (Test-Path $flag) { Remove-Item $flag -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $bot 'storage\logs') | Out-Null
$outLog = Join-Path $bot 'storage\logs\cmd_startup_capture.txt'
# تشغيل لقطة إقلاع قصيرة لمعرفة الأخطاء
$py = 'py'
try { & $py -V | Out-Null } catch { $py = 'python' }
Set-Location $bot
$env:PYTHONPATH = $bot
$env:PYTHONIOENCODING = 'utf-8'
# تثبيت سريع ثم تشغيل مؤقت 45 ثانية لالتقاط المخرجات
& $py -m pip install -r requirements.txt -q 2>&1 | Out-File $outLog -Encoding utf8
"===== BOOT =====" | Out-File $outLog -Append -Encoding utf8
$p = Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory $bot -RedirectStandardOutput $outLog -RedirectStandardError (Join-Path $bot 'storage\logs\cmd_startup_err.txt') -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 35
if (-not $p.HasExited) {
  Write-Host ("RUNNING pid=" + $p.Id)
} else {
  Write-Host ("EXITED code=" + $p.ExitCode)
}
Write-Host '--- STARTUP OUT ---'
Get-Content $outLog -Tail 80 -ErrorAction SilentlyContinue
Write-Host '--- STARTUP ERR ---'
Get-Content (Join-Path $bot 'storage\logs\cmd_startup_err.txt') -Tail 40 -ErrorAction SilentlyContinue
# إن خرج، أعد التشغيل في نافذة ظاهرة عبر VBS/bat
if ($p.HasExited) {
  Start-Process -FilePath (Join-Path $bot '00_START.bat') -WorkingDirectory $bot
  Write-Host 'RESTARTED_VIA_00_START'
} else {
  Write-Host 'LEFT_RUNNING_HIDDEN_OK'
}
"""
    print(run_ps(client, start, timeout=240))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
