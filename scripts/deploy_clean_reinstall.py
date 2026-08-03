"""
إعادة تثبيت نظيفة كاملة على Windows VPS:
1) إيقاف كل شيء
2) نسخ احتياطي لـ .env + قاعدة البيانات فقط
3) حذف مجلد البوت القديم بالكامل + المجلدات القديمة
4) تثبيت نسخة نظيفة من المستودع المحلي
5) استعادة .env/DB + تشغيل مثيل واحد + نافذة إشارات واحدة
"""

from __future__ import annotations

import io
import os
import sys
import tarfile
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

HOST = os.getenv("WIN_HOST", "").strip()
USER = os.getenv("WIN_USER", "").strip()
PASSWORD = os.getenv("WIN_PASSWORD", "")
KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
BACKUP = r"C:\ProgramData\GoldenShield\_clean_reinstall_backup"

EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".cursor",
    "htmlcov",
    "tests",
    ".github",
    "docs",
    "saas",
    "agent-transcripts",
    "storage",
    "node_modules",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
EXCLUDE_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".dockerignore",
    "SESSION_STATE.md",
    "pytest.ini",
    ".env",
}


def should_skip(rel: Path) -> bool:
    if set(rel.parts) & EXCLUDE_DIRS:
        return True
    if any(p.startswith("scripts\\_tmp") or p.startswith("scripts/_tmp") for p in [str(rel).replace("\\", "/")]):
        if "/_tmp" in str(rel).replace("\\", "/") or str(rel).replace("\\", "/").startswith("scripts/_tmp"):
            return True
    if rel.name.startswith("_tmp_"):
        return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    if rel.name in EXCLUDE_FILES:
        return True
    return False


def build_archive() -> bytes:
    buf = io.BytesIO()
    count = 0
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if should_skip(rel):
                continue
            tar.add(path, arcname=rel.as_posix())
            count += 1
    data = buf.getvalue()
    print(f"ARCHIVE_FILES={count} SIZE_KB={len(data)/1024:.1f}")
    return data


def merge_env(server_env: str, local_env: dict[str, str]) -> str:
    """ادمج .env السيرفر مع مفاتيح التشغيل النظيفة — بدون طباعة أسرار."""
    merged: dict[str, str] = {}
    for line in server_env.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        merged[k.strip()] = v.strip()

    # مفاتيح حساسة من المحلي فقط إن غابت على السيرفر
    for key in (
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_BACKUP_CHANNEL_ID",
        "TELEGRAM_BOT_USERNAME",
    ):
        if not merged.get(key) and local_env.get(key):
            merged[key] = local_env[key]

    # إعدادات التشغيل النظيفة المطلوبة
    forced = {
        "ENV": "production",
        "EXECUTION_MODE": "live",
        "EXECUTION_BACKEND": "binance",
        "BINANCE_DEMO_TRADING": "true",
        "MT5_ENABLED": "false",
        "BOT_AUTO_SYNC_MT5": "false",
        "MT5_ATTACH_SL_TP": "false",
        "BOT_FORCE_ACTIVE": "true",
        "TELEGRAM_LIVE_SIGNALS": "true",
        "TELEGRAM_LIVE_SIGNALS_SECONDS": "0.8",
        "TELEGRAM_LIVE_POSITIONS_SECONDS": "0.8",
        "TELEGRAM_SEND_CYCLE_SIGNALS": "true",
        "LOOP_INTERVAL_SECONDS": "15",
        "DB_PATH": r"C:\GoldenShield_Binance\storage\db\goldenshield.db",
        "GOLDENSHIELD_OFFICIAL_ROOT": KEEP,
        "GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT": "true",
        "GOLDENSHIELD_LOCK_FAIL_CLOSED": "true",
        "MANUAL_MAX_CONCURRENT_POSITIONS": merged.get("MANUAL_MAX_CONCURRENT_POSITIONS", "0"),
        "AUTO_ENTRY_MIN_PERCENT": merged.get("AUTO_ENTRY_MIN_PERCENT", "90"),
    }
    merged.update(forced)

    lines = [f"{k}={v}" for k, v in sorted(merged.items())]
    return "\n".join(lines) + "\n"


def load_local_env() -> dict[str, str]:
    out: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not HOST or not USER or not PASSWORD:
        print("Missing WIN_HOST/WIN_USER/WIN_PASSWORD")
        return 1

    local_env = load_local_env()
    archive = build_archive()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60, allow_agent=False, look_for_keys=False)

    # ---- remote cleanup + install script ----
    remote_ps = r"""
$ErrorActionPreference='Continue'
$keep='C:\GoldenShield_Binance'
$backup='C:\ProgramData\GoldenShield\_clean_reinstall_backup'
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$old=($keep + '_OLD_' + $stamp)
New-Item -ItemType Directory -Force -Path $backup,(Join-Path $backup 'db'),(Join-Path $backup 'reports') | Out-Null
function WLog($m){ Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) }

WLog '=== STOP ALL ==='
foreach($tn in @(
  'GoldenShieldBotOfficial','GoldenShieldWatchdog','GoldenShieldStatusWindow',
  'GoldenShieldLiveConsole','GoldenShieldBotVisible','GoldenShieldBot','GoldenShieldBotBoot'
)){
  schtasks /End /TN $tn /F 2>$null | Out-Null
  schtasks /Delete /TN $tn /F 2>$null | Out-Null
}
$myPid = $PID
Get-CimInstance Win32_Process | Where-Object {
  $_.ProcessId -ne $myPid -and
  $_.ParentProcessId -ne $myPid -and
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match 'run_official_bot' -or
    $_.CommandLine -match 'BOT_WINDOW' -or
    $_.CommandLine -match '00_LIVE_CONSOLE' -or
    $_.CommandLine -match 'START_BOT\.bat' -or
    $_.CommandLine -match 'REST_BOT\.bat' -or
    ($_.CommandLine -match 'C:\\GoldenShield_Binance' -and $_.Name -match 'python|cmd|powershell')
  ) -and
  $_.CommandLine -notmatch '_clean_prep|_clean_finish|_clean_extract|ProgramData\\GoldenShield\\_clean'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 3
WLog 'STOP_DONE'

WLog '=== BACKUP ENV+DB ==='
if(Test-Path (Join-Path $keep '.env')){
  Copy-Item (Join-Path $keep '.env') (Join-Path $backup ('.env.'+$stamp)) -Force
  Copy-Item (Join-Path $keep '.env') (Join-Path $backup '.env.latest') -Force
  WLog 'env_backed_up'
} else { WLog 'env_missing' }
$db=Join-Path $keep 'storage\db\goldenshield.db'
if(Test-Path $db){
  Copy-Item $db (Join-Path $backup 'db\goldenshield.db') -Force
  WLog 'db_backed_up'
} else { WLog 'db_missing' }
$rep=Join-Path $keep 'storage\reports'
if(Test-Path $rep){
  Copy-Item $rep (Join-Path $backup 'reports') -Recurse -Force -EA SilentlyContinue
  WLog 'reports_backed_up'
}

WLog '=== RENAME OLD KEEP ==='
if(Test-Path $keep){
  try {
    Rename-Item -LiteralPath $keep -NewName (Split-Path $old -Leaf) -Force -EA Stop
    WLog ('renamed_to=' + $old)
  } catch {
    WLog ('rename_fail=' + $_.Exception.Message)
    WLog 'fallback_delete_contents'
    cmd /c ("rmdir /s /q `"" + $keep + "`"")
  }
}

WLog '=== DELETE OTHER OLD FOLDERS ==='
$targets = @(
  'C:\GoldenShield',
  'C:\GSBot'
)
$targets += @(Get-ChildItem 'C:\' -Directory -EA SilentlyContinue | Where-Object {
  $_.Name -match '^GoldenShield' -and $_.FullName -ne $keep -and $_.FullName -ne $old
} | Select-Object -ExpandProperty FullName)
$targets += @(Get-ChildItem 'C:\Users\Administrator\Downloads' -Recurse -Directory -EA SilentlyContinue | Where-Object {
  $_.Name -match 'GoldenShield|CONTABO_DEMO|GOLDENSHIELD'
} | Select-Object -ExpandProperty FullName)
foreach($t in ($targets | Select-Object -Unique)){
  if(-not $t){ continue }
  if($t -eq $keep){ continue }
  if(Test-Path $t){
    WLog ('DELETE ' + $t)
    cmd /c ("rmdir /s /q `"" + $t + "`"")
    if(Test-Path $t){ Remove-Item -LiteralPath $t -Recurse -Force -EA SilentlyContinue }
    if(Test-Path $t){ WLog ('FAIL_DELETE ' + $t) } else { WLog ('OK_DELETE ' + $t) }
  }
}

# احذف المجلد القديم بعد التأكد لاحقاً — نبقيه مؤقتاً حتى نجاح التثبيت
WLog '=== PREPARE FRESH DIR ==='
New-Item -ItemType Directory -Force -Path $keep,(Join-Path $keep 'storage\db'),(Join-Path $keep 'storage\logs'),(Join-Path $keep 'storage\runtime'),(Join-Path $keep 'storage\reports') | Out-Null
Write-Host 'CLEAN_PREP_OK'
"""

    sftp = ssh.open_sftp()
    # ensure remote dirs
    for d in (r"C:\ProgramData\GoldenShield",):
        try:
            sftp.stat(d)
        except OSError:
            try:
                sftp.mkdir(d)
            except OSError:
                pass

    prep = r"C:\ProgramData\GoldenShield\_clean_prep.ps1"
    with sftp.file(prep, "w") as fh:
        fh.write(remote_ps.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("=== PREP / WIPE ===")
    _, o, e = ssh.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{prep}"', timeout=600
    )
    prep_out = (o.read() + e.read()).decode("utf-8", "replace")
    print(prep_out[-5000:])
    if "CLEAN_PREP_OK" not in prep_out:
        print("PREP_FAILED")
        ssh.close()
        return 1

    # upload archive
    print("=== UPLOAD ARCHIVE ===")
    remote_tar = r"C:\ProgramData\GoldenShield\_clean_deploy.tgz"
    with sftp.file(remote_tar, "wb") as rf:
        rf.write(archive)
    print(f"UPLOADED_TGZ={len(archive)}")

    # read server env backup if exists
    server_env_text = ""
    try:
        with sftp.file(BACKUP + r"\.env.latest", "r") as ef:
            server_env_text = ef.read().decode("utf-8", "replace")
        print("SERVER_ENV_BACKUP=yes")
    except OSError:
        print("SERVER_ENV_BACKUP=no — will use local keys merge")

    env_text = merge_env(server_env_text, local_env)
    env_remote = KEEP + r"\.env"
    # write env after extract

    finish = r"""
$ErrorActionPreference='Continue'
$keep='C:\GoldenShield_Binance'
$backup='C:\ProgramData\GoldenShield\_clean_reinstall_backup'
$tar='C:\ProgramData\GoldenShield\_clean_deploy.tgz'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
function WLog($m){ Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) }

WLog '=== EXTRACT ==='
Set-Location $keep
tar -xzf $tar
if(-not (Test-Path (Join-Path $keep 'main.py'))){ Write-Host 'EXTRACT_FAIL'; exit 1 }
Remove-Item $tar -Force -EA SilentlyContinue
WLog 'EXTRACT_OK'

WLog '=== RESTORE DB/REPORTS ==='
$dbSrc=Join-Path $backup 'db\goldenshield.db'
$dbDst=Join-Path $keep 'storage\db\goldenshield.db'
New-Item -ItemType Directory -Force -Path (Split-Path $dbDst) | Out-Null
if(Test-Path $dbSrc){ Copy-Item $dbSrc $dbDst -Force; WLog 'DB_RESTORED' } else { WLog 'DB_NEW' }
$repSrc=Join-Path $backup 'reports'
$repDst=Join-Path $keep 'storage\reports'
if(Test-Path $repSrc){ Copy-Item $repSrc $repDst -Recurse -Force -EA SilentlyContinue; WLog 'REPORTS_RESTORED' }

WLog '=== BOOTSTRAP ==='
$env:PYTHONPATH=$keep
$env:GOLDENSHIELD_OFFICIAL_ROOT=$keep
Set-Location $keep
if(Test-Path $py){
  & $py -m pip install -r requirements.txt --disable-pip-version-check 2>&1 | Select-Object -Last 15
  & $py scripts\bootstrap_storage.py 2>&1
} else {
  py -m pip install -r requirements.txt --disable-pip-version-check 2>&1 | Select-Object -Last 15
  py scripts\bootstrap_storage.py 2>&1
}

WLog '=== REGISTER HIDDEN WORKER ==='
$worker=Join-Path $keep 'run_official_bot.ps1'
if(-not (Test-Path $worker)){ Write-Host 'WORKER_MISSING'; exit 1 }
$tr=('powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $worker)
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
try {
  $t=Get-ScheduledTask -TaskName 'GoldenShieldBotOfficial'
  $t.Settings.Hidden=$true
  $t.Settings.ExecutionTimeLimit='PT0S'
  $t | Set-ScheduledTask | Out-Null
} catch {}

# اختصارات سطح المكتب الثلاثة فقط
$desk=[Environment]::GetFolderPath('Desktop')
$w=New-Object -ComObject WScript.Shell
foreach($pair in @(
  @('START BOT.lnk','START_BOT.bat'),
  @('STOP BOT.lnk','STOP_BOT.bat'),
  @('REST BOT.lnk','REST_BOT.bat')
)){
  $sc=$w.CreateShortcut((Join-Path $desk $pair[0]))
  $sc.TargetPath=(Join-Path $keep $pair[1])
  $sc.WorkingDirectory=$keep
  $sc.Save()
}

Remove-Item (Join-Path $keep 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $keep 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue

schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
WLog 'BOT_START_REQUESTED'
Start-Sleep 18

# نافذة إشارات واحدة
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
$future=(Get-Date).AddMinutes(5).ToString('HH:mm')
$win=Join-Path $keep 'BOT_WINDOW.bat'
schtasks /Delete /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldStatusWindow /TR ('"' + $win + '"') /SC ONCE /ST $future /RL HIGHEST /IT /F | Out-Null
schtasks /Run /TN GoldenShieldStatusWindow | Out-Null
Start-Sleep 4

# احذف المجلد القديم بعد النجاح
Get-ChildItem 'C:\' -Directory -EA SilentlyContinue | Where-Object { $_.Name -match '^GoldenShield_Binance_OLD_' } | ForEach-Object {
  WLog ('DELETE_OLD ' + $_.FullName)
  cmd /c ("rmdir /s /q `"" + $_.FullName + "`"")
  if(Test-Path $_.FullName){ Remove-Item -LiteralPath $_.FullName -Recurse -Force -EA SilentlyContinue }
}

$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
$wins=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)' })
Write-Host ('MAIN_COUNT=' + $mains.Count)
Write-Host ('WINDOW_PROCS=' + $wins.Count)
Write-Host ('MAIN_PY=' + (Test-Path (Join-Path $keep 'main.py')))
Write-Host ('START_BOT=' + (Test-Path (Join-Path $keep 'START_BOT.bat')))
Write-Host ('BOT_WINDOW=' + (Test-Path (Join-Path $keep 'BOT_WINDOW.bat')))
Write-Host ('ENV=' + (Test-Path (Join-Path $keep '.env')))
Write-Host ('DB=' + (Test-Path (Join-Path $keep 'storage\db\goldenshield.db')))
$oldLeft=@(Get-ChildItem 'C:\' -Directory -EA SilentlyContinue | Where-Object { $_.Name -match '^GoldenShield_Binance_OLD_' })
Write-Host ('OLD_LEFT=' + $oldLeft.Count)
Start-Sleep 12
$board=Join-Path $keep 'storage\runtime\signals_board.txt'
Write-Host ('BOARD=' + (Test-Path $board))
if(Test-Path $board){ Get-Content $board -Encoding UTF8 -TotalCount 12 }
if($mains.Count -eq 1 -and (Test-Path (Join-Path $keep 'main.py')) -and (Test-Path (Join-Path $keep '.env'))){
  Write-Host 'CLEAN_REINSTALL_OK'
} else {
  Write-Host 'CLEAN_REINSTALL_CHECK'
}
"""

    # write merged env into KEEP before finish? finish extracts first — write env after extract in python
    fin = r"C:\ProgramData\GoldenShield\_clean_finish.ps1"
    with sftp.file(fin, "w") as fh:
        fh.write(finish.replace("\r\n", "\n").replace("\n", "\r\n"))
    sftp.close()

    print("=== EXTRACT + START ===")
    # First extract only via small command, then write env, then rest... 
    # Simpler: run finish which extracts; then we need env present BEFORE bot start.
    # Patch finish flow: extract in python side first.

    extract_ps = rf"""
$keep='{KEEP}'
$tar='C:\ProgramData\GoldenShield\_clean_deploy.tgz'
New-Item -ItemType Directory -Force -Path $keep | Out-Null
Set-Location $keep
tar -xzf $tar
Write-Host ('MAIN=' + (Test-Path (Join-Path $keep 'main.py')))
Write-Host 'EXTRACT_DONE'
"""
    extract_remote = r"C:\ProgramData\GoldenShield\_clean_extract.ps1"
    sftp = ssh.open_sftp()
    with sftp.file(extract_remote, "w") as fh:
        fh.write(extract_ps.replace("\r\n", "\n").replace("\n", "\r\n"))
    _, o, e = ssh.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{extract_remote}"', timeout=300
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))

    # write .env
    with sftp.file(KEEP + r"\.env", "w") as ef:
        ef.write(env_text)
    print("ENV_WRITTEN")

    with sftp.file(fin, "w") as fh:
        # finish without re-extract — restore db, pip, start
        finish2 = r"""
$ErrorActionPreference='Continue'
$keep='C:\GoldenShield_Binance'
$backup='C:\ProgramData\GoldenShield\_clean_reinstall_backup'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
function WLog($m){ Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) }

if(-not (Test-Path (Join-Path $keep 'main.py'))){ Write-Host 'EXTRACT_FAIL'; exit 1 }
Remove-Item 'C:\ProgramData\GoldenShield\_clean_deploy.tgz' -Force -EA SilentlyContinue

WLog '=== RESTORE DB/REPORTS ==='
New-Item -ItemType Directory -Force -Path (Join-Path $keep 'storage\db'),(Join-Path $keep 'storage\logs'),(Join-Path $keep 'storage\runtime'),(Join-Path $keep 'storage\reports') | Out-Null
$dbSrc=Join-Path $backup 'db\goldenshield.db'
$dbDst=Join-Path $keep 'storage\db\goldenshield.db'
if(Test-Path $dbSrc){ Copy-Item $dbSrc $dbDst -Force; WLog 'DB_RESTORED' } else { WLog 'DB_NEW' }
$repSrc=Join-Path $backup 'reports'
if(Test-Path $repSrc){ Copy-Item $repSrc (Join-Path $keep 'storage\reports') -Recurse -Force -EA SilentlyContinue; WLog 'REPORTS_RESTORED' }

WLog '=== PIP + BOOTSTRAP ==='
$env:PYTHONPATH=$keep
$env:GOLDENSHIELD_OFFICIAL_ROOT=$keep
Set-Location $keep
& $py -m pip install -r requirements.txt --disable-pip-version-check 2>&1 | Select-Object -Last 20
& $py scripts\bootstrap_storage.py 2>&1

WLog '=== TASK + SHORTCUTS ==='
foreach($tn in @('GoldenShieldBotOfficial','GoldenShieldStatusWindow','GoldenShieldWatchdog','GoldenShieldLiveConsole','GoldenShieldBotVisible')){
  schtasks /End /TN $tn /F 2>$null | Out-Null
  schtasks /Delete /TN $tn /F 2>$null | Out-Null
}
$worker=Join-Path $keep 'run_official_bot.ps1'
$tr=('powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $worker)
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
try { $t=Get-ScheduledTask GoldenShieldBotOfficial; $t.Settings.Hidden=$true; $t.Settings.ExecutionTimeLimit='PT0S'; $t|Set-ScheduledTask|Out-Null } catch {}

$desk=[Environment]::GetFolderPath('Desktop')
$w=New-Object -ComObject WScript.Shell
foreach($pair in @(@('START BOT.lnk','START_BOT.bat'),@('STOP BOT.lnk','STOP_BOT.bat'),@('REST BOT.lnk','REST_BOT.bat'))){
  $sc=$w.CreateShortcut((Join-Path $desk $pair[0])); $sc.TargetPath=(Join-Path $keep $pair[1]); $sc.WorkingDirectory=$keep; $sc.Save()
}

Remove-Item (Join-Path $keep 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $keep 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 20

Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
$future=(Get-Date).AddMinutes(5).ToString('HH:mm')
schtasks /Create /TN GoldenShieldStatusWindow /TR ('"' + (Join-Path $keep 'BOT_WINDOW.bat') + '"') /SC ONCE /ST $future /RL HIGHEST /IT /F | Out-Null
schtasks /Run /TN GoldenShieldStatusWindow | Out-Null
Start-Sleep 4

Get-ChildItem 'C:\' -Directory -EA SilentlyContinue | Where-Object { $_.Name -match '^GoldenShield_Binance_OLD_' } | ForEach-Object {
  WLog ('DELETE_OLD ' + $_.FullName)
  cmd /c ("rmdir /s /q `"" + $_.FullName + "`"")
  if(Test-Path $_.FullName){ Remove-Item -LiteralPath $_.FullName -Recurse -Force -EA SilentlyContinue }
}

$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
$wins=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)' })
Write-Host ('MAIN_COUNT=' + $mains.Count)
Write-Host ('WINDOW_PROCS=' + $wins.Count)
Write-Host ('MAIN_PY=' + (Test-Path (Join-Path $keep 'main.py')))
Write-Host ('START_BOT=' + (Test-Path (Join-Path $keep 'START_BOT.bat')))
Write-Host ('ENV=' + (Test-Path (Join-Path $keep '.env')))
Write-Host ('DB=' + (Test-Path (Join-Path $keep 'storage\db\goldenshield.db')))
$oldLeft=@(Get-ChildItem 'C:\' -Directory -EA SilentlyContinue | Where-Object { $_.Name -match '^GoldenShield_Binance_OLD_|^GoldenShield$' })
Write-Host ('OLD_LEFT=' + $oldLeft.Count)
$board=Join-Path $keep 'storage\runtime\signals_board.txt'
$deadline=(Get-Date).AddSeconds(40)
while((Get-Date) -lt $deadline -and -not ((Test-Path $board) -and ((Get-Content $board -Raw -EA SilentlyContinue) -match 'score:'))){ Start-Sleep 3 }
Write-Host ('BOARD=' + (Test-Path $board))
if(Test-Path $board){ Get-Content $board -Encoding UTF8 -TotalCount 14 }
if($mains.Count -eq 1 -and (Test-Path (Join-Path $keep 'main.py')) -and (Test-Path (Join-Path $keep '.env')) -and $oldLeft.Count -eq 0){
  Write-Host 'CLEAN_REINSTALL_OK'
} else {
  Write-Host 'CLEAN_REINSTALL_CHECK'
}
"""
        fh.write(finish2.replace("\r\n", "\n").replace("\n", "\r\n"))
    sftp.close()

    _, o, e = ssh.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{fin}"', timeout=900
    )
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out[-8000:])
    ssh.close()

    if "CLEAN_REINSTALL_OK" in out:
        print("DONE: clean reinstall OK")
        return 0
    print("DONE: check needed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
