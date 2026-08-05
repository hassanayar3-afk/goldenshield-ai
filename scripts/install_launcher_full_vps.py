"""تنظيف launchers القديمة على VPS وتثبيت الحزمة الكاملة ENTERPRISE_FULL."""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"

UPLOADS = [
    "run_official_bot.ps1",
    "run_official_bot.bat",
    "START_BOT.bat",
    "STOP_BOT.bat",
    "REST_BOT.bat",
    "run.bat",
    "00_START.bat",
    "00_START_KEEP_OPEN.bat",
]

ENV_MAP = {
    "BOT_FORCE_ACTIVE": "true",
    "HYBRID_SIGNAL_MODE": "true",
    "TELEGRAM_LIVE_SIGNALS": "true",
    "TELEGRAM_LIVE_SIGNALS_SECONDS": "15",
    "TELEGRAM_LIVE_POSITIONS_SECONDS": "1",
    "PROJECT_REFERENCE_CAPITAL": "5000",
    "PROJECT_MIN_TRADE_NOTIONAL": "25",
    "PROJECT_MIN_EXCHANGE_NOTIONAL": "5",
    "AUTO_ENTRY_MIN_PERCENT": "90",
    "TELEGRAM_SIGNAL_MIN_PERCENT": "70",
    "MANUAL_ENTRY_REQUIRED": "false",
    "ENTERPRISE_PIPELINE_ENABLED": "true",
    "SSOT_SYNC_ENABLED": "true",
    "POST_MORTEM_ENGINE_ACTIVE": "true",
    "CIRCUIT_BREAKER_MAX_LOSSES": "3",
}

# ملفات تشغيل قديمة متعارضة — تُستبدل بإعادة توجيه أو تُحذف إن كانت نسخاً مبعثرة
REDIRECT_WRAPPER = """@echo off
rem DEPRECATED — يوجّه إلى START_BOT.bat الرسمي فقط
echo [GS] %~nx0 deprecated — redirecting to START_BOT.bat
call "%~dp0START_BOT.bat"
"""

VERIFY = r'''
import os, sys
os.chdir(r"C:\GoldenShield_Binance")
sys.path.insert(0, r"C:\GoldenShield_Binance")
fails=[]
def ok(n,c,d=""):
    print(("PASS " if c else "FAIL ")+n+((" "+d) if d else ""))
    if not c: fails.append(n)

w=open("run_official_bot.ps1",encoding="utf-8",errors="replace").read()
ok("WORKER_FULL", "GS_OFFICIAL_WORKER_v2026_08_ENTERPRISE_FULL" in w)
ok("WORKER_PREFLIGHT_FULL", "ENTERPRISE_FULL" in w or "ANALYSIS_TIMEFRAMES" in w)
ok("WORKER_ENV_70", "TELEGRAM_SIGNAL_MIN_PERCENT" in w and "70" in w)
ok("WORKER_ENV_90", "AUTO_ENTRY_MIN_PERCENT" in w and "90" in w)
ok("WORKER_PM", "POST_MORTEM" in w)
ok("WORKER_CB", "CIRCUIT_BREAKER_MAX_LOSSES" in w)
ok("WORKER_PIPELINE", "ENTERPRISE_PIPELINE_ENABLED" in w)

s=open("START_BOT.bat",encoding="utf-8",errors="replace").read()
ok("START_FULL", "ENTERPRISE_FULL" in s)
ok("START_RULES", "PROJECT_REFERENCE_CAPITAL" in s and "CIRCUIT_BREAKER" in s)

r=open("REST_BOT.bat",encoding="utf-8",errors="replace").read()
ok("REST_FULL", "ENTERPRISE_FULL" in r and "HYBRID_SIGNAL_MODE" in r)

env=open(".env",encoding="utf-8",errors="replace").read().replace(" ","")
ok("ENV_AUTO90", "AUTO_ENTRY_MIN_PERCENT=90" in env)
ok("ENV_NOTIFY70", "TELEGRAM_SIGNAL_MIN_PERCENT=70" in env)
ok("ENV_PIPELINE", "ENTERPRISE_PIPELINE_ENABLED=true" in env.lower() or "ENTERPRISE_PIPELINE_ENABLED=true" in env)
ok("ENV_PM", "POST_MORTEM_ENGINE_ACTIVE" in env)

from config.project_rules import load_project_rules
rules=load_project_rules()
ok("RULES_CAP", float(rules.reference_capital)>=5000)
ok("RULES_MIN", float(rules.min_trade_notional)>=25)
ok("RULES_HYBRID", rules.hybrid_mode and rules.enterprise_pipeline)

print("FAILS", len(fails))
if fails:
    print("FAILED", ",".join(fails)); raise SystemExit(1)
print("LAUNCHER_FULL_INSTALL_OK")
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

    # 1) Stop bot safely + clean old conflicting launchers (keep DB)
    clean_ps = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
Write-Output '=== STOP & CLEAN OLD LAUNCHERS ==='
schtasks /End /TN 'GoldenShieldBotOfficial' /F 2>$null
schtasks /End /TN 'GoldenShieldLiveConsole' /F 2>$null
schtasks /End /TN 'GoldenShieldStatusWindow' /F 2>$null
Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'main\.py|run_official_bot')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep -Seconds 3

# أقفال تشغيل فقط
$rt=Join-Path $g 'storage\runtime'
Remove-Item (Join-Path $rt 'user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $rt 'bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '*.tmp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '*.temp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_worker_preflight.py' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_check_*.ps1' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_fix_*.ps1' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_env_*.ps1' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_gaps*.ps1' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_monitor*.ps1' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_verify*.py' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '_e2e*.py' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue

# أرشفة launchers قديمة متعارضة (لا تلمس DB)
$arch=Join-Path $g 'storage\runtime\_archived_launchers'
New-Item -ItemType Directory -Path $arch -Force | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
foreach($name in @(
  '00_START_AUTO.bat','scripts\00_START_AUTO.bat','INSTALL_AUTOSTART.bat',
  '00_START_KEEP_OPEN.bat','run.ps1'
)){
  $p=Join-Path $g $name
  if(Test-Path $p){
    $dest=Join-Path $arch ($stamp + '_' + ($name -replace '[\\/]','_'))
    try { Move-Item $p $dest -Force; Write-Output ('ARCHIVED ' + $name) } catch { Write-Output ('ARCHIVE_SKIP ' + $name) }
  }
}
Write-Output 'CLEAN_DONE'
Write-Output ('DB_EXISTS=' + (Test-Path (Join-Path $g 'storage\db\goldenshield.db')))
"""
    sftp = client.open_sftp()
    with sftp.open(f"{KEEP}\\storage\\runtime\\_clean_launchers.ps1", "w") as f:
        f.write(clean_ps.encode("utf-8"))
    sftp.close()
    _i, o, e = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{KEEP}\storage\runtime\_clean_launchers.ps1"',
        timeout=90,
    )
    print(o.read().decode("utf-8", errors="replace"))
    if e.read():
        pass

    # 2) Upload official launchers
    sftp = client.open_sftp()
    for rel in UPLOADS:
        local = ROOT / rel
        if not local.is_file():
            print("SKIP", rel)
            continue
        remote = f"{KEEP}\\{rel.replace('/', chr(92))}"
        sftp.put(str(local), remote)
        print("UPLOADED", rel)

    # Ensure deprecated wrappers redirect to START_BOT
    for name in ("run.bat", "00_START.bat", "00_START_KEEP_OPEN.bat"):
        remote = f"{KEEP}\\{name}"
        sftp.putfo(io.BytesIO(REDIRECT_WRAPPER.encode("utf-8")), remote)
        print("WRAPPER", name)

    # Sync .env keys
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
    with sftp.open(env_path, "w") as f:
        f.write(("\n".join(out_lines) + "\n").encode("utf-8"))
    print("ENV_RULES_SYNCED")

    # Upload verify
    sftp.putfo(io.BytesIO(VERIFY.encode("utf-8")), f"{KEEP}\\storage\\runtime\\_verify_launcher_full.py")
    sftp.close()

    # 3) Verify then restart
    cmd = (
        rf'cmd /c "cd /d {KEEP} && set PYTHONPATH={KEEP} && '
        r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe "
        r'storage\runtime\_verify_launcher_full.py"'
    )
    _i, stdout, stderr = client.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[-1200:])
    print("VERIFY_EXIT", code)

    restart_ps = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$worker=Join-Path $g 'run_official_bot.ps1'
schtasks /Delete /TN 'GoldenShieldBotOfficial' /F 2>$null
schtasks /Create /TN 'GoldenShieldBotOfficial' /TR "powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$worker`"" /SC ONSTART /RL HIGHEST /F | Out-Null
try {
  $t=Get-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA Stop
  $t.Settings.Hidden=$true
  $t.Settings.ExecutionTimeLimit='PT0S'
  $t | Set-ScheduledTask | Out-Null
} catch {}
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN 'GoldenShieldBotOfficial' | Out-Null
Start-Sleep -Seconds 14
$mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.Name -match '^(python|pythonw|py)\.exe$' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
} | Sort-Object ProcessId)
if($mains.Count -gt 1){
  $keep=$mains[0]
  foreach($p in $mains){ if($p.ProcessId -ne $keep.ProcessId){ Stop-Process -Id $p.ProcessId -Force -EA SilentlyContinue } }
  Start-Sleep -Seconds 2
  $mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.CommandLine -match 'main\.py' })
}
$w=Get-Content $worker -Raw -EA SilentlyContinue
Write-Output ('WORKER_TAG=' + ($(if($w -match 'ENTERPRISE_FULL'){'ENTERPRISE_FULL'}elseif($w -match 'ENTERPRISE'){'ENTERPRISE'}else{'UNKNOWN'})))
Write-Output ('MAIN=' + $mains.Count)
if(($mains.Count -eq 1) -and ($w -match 'ENTERPRISE_FULL')){ Write-Output 'SERVER_LAUNCHER_FULL_OK' } else { Write-Output 'SERVER_LAUNCHER_WARN' }
Remove-Item (Join-Path $g 'storage\runtime\_verify_launcher_full.py') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\_clean_launchers.ps1') -Force -EA SilentlyContinue
"""
    sftp = client.open_sftp()
    with sftp.open(f"{KEEP}\\storage\\runtime\\_restart_full.ps1", "w") as f:
        f.write(restart_ps.encode("utf-8"))
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{KEEP}\storage\runtime\_restart_full.ps1"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
