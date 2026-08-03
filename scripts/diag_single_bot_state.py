"""تشخيص سريع: قواعد البيانات، المراكز، العمليات، تعارض تيليجرام."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

HOST = os.getenv("WIN_HOST", "").strip()
USER = os.getenv("WIN_USER", "").strip()
PASSWORD = os.getenv("WIN_PASSWORD", "")

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
Write-Host '=== DIAG_SINGLE_BOT ==='

Write-Host '--- PROCESSES ---'
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'main\.py|00_START|run_official|LIVE_CONSOLE')
} | ForEach-Object {
  Write-Host ('PID=' + $_.ProcessId + ' NAME=' + $_.Name)
  Write-Host $_.CommandLine
}

Write-Host '--- TASKS ---'
schtasks /Query /TN GoldenShieldBotOfficial /FO LIST /V 2>$null | Select-String -Pattern 'Status|Task To Run|Last Run'
schtasks /Query /TN GoldenShieldWatchdog /FO LIST 2>$null | Select-String -Pattern 'Status|Next Run'

Write-Host '--- ENV KEYS ---'
$envp = Join-Path $good '.env'
Select-String -Path $envp -Pattern '^(DB_PATH|TELEGRAM_|EXECUTION_|BINANCE_DEMO|GOLDENSHIELD_)' | ForEach-Object { $_.Line }

Write-Host '--- DB FILES ---'
Get-ChildItem (Join-Path $good 'storage\db') -Force -EA SilentlyContinue | ForEach-Object {
  Write-Host ($_.FullName + ' size=' + $_.Length + ' mtime=' + $_.LastWriteTime)
}

Write-Host '--- PYTHON DB CHECK ---'
Set-Location $good
$env:PYTHONPATH=$good
$env:PYTHONIOENCODING='utf-8'
& $py -c @"
import os, sqlite3
from pathlib import Path
from config.settings import get_settings
s=get_settings()
print('cwd', Path.cwd())
print('settings.db_path', s.db_path)
print('abs', Path(s.db_path).resolve() if s.db_path else None)
p=Path(s.db_path)
if not p.is_absolute():
    p=(Path.cwd()/p).resolve()
print('resolved', p, 'exists', p.exists(), 'size', p.stat().st_size if p.exists() else 0)
con=sqlite3.connect(str(p))
tables=[r[0] for r in con.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]
print('tables', tables)
for t in tables:
    try:
        n=con.execute(f'SELECT COUNT(*) FROM [{t}]').fetchone()[0]
        if n: print(f'  {t}={n}')
    except Exception as e:
        print('err', t, e)
# trades open
cols=[r[1] for r in con.execute('PRAGMA table_info(trades)')]
print('trades_cols', cols)
if 'status' in cols:
    for row in con.execute('SELECT status, COUNT(*) FROM trades GROUP BY status'):
        print('status', row)
    for row in con.execute(\"SELECT id, symbol, status FROM trades WHERE status LIKE '%open%' OR status='OPEN' LIMIT 20\"):
        print('open_row', row)
"@

Write-Host '--- LOG CONFLICT ---'
$log=Join-Path $good 'storage\logs\bot_stdout.log'
if (Test-Path $log) {
  Select-String -Path $log -Pattern 'Conflict|getUpdates|Single-instance|بوت آخر|restore|synced|Open positions' |
    Select-Object -Last 25 | ForEach-Object { $_.Line }
  Write-Host 'LOG_TAIL:'
  Get-Content $log -Tail 8
}

Write-Host 'DIAG_DONE'
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    try:
        remote = r"C:\ProgramData\GoldenShield\diag_single.ps1"
        sftp = ssh.open_sftp()
        with sftp.file(remote, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        _, o, e = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
            timeout=180,
        )
        text = (o.read() + e.read()).decode("utf-8", errors="replace")
        print(text.encode("ascii", errors="replace").decode("ascii"))
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
