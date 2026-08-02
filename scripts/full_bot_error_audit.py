"""فحص شامل لأخطاء البوت على VPS — أسباب جذرية قابلة للإصلاح."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
Set-Location $good
$env:PYTHONPATH=$good
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'

Write-Host '===== 1) PROCESSES ====='
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match 'GOLDENSHIELD' -or
    $_.CommandLine -match '00_START'
  )
} | ForEach-Object {
  Write-Host ('PID=' + $_.ProcessId + ' PPID=' + $_.ParentProcessId + ' NAME=' + $_.Name)
  Write-Host $_.CommandLine
}

Write-Host '===== 2) PATH/FLAGS ====='
Write-Host ('CWD_EXISTS=' + (Test-Path $good))
Write-Host ('USER_STOPPED=' + (Test-Path 'storage\runtime\user_stopped.flag'))
Write-Host ('LOCK=' + (Test-Path 'storage\runtime\bot_instance.lock'))
Write-Host 'SCHEDULED:'
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match 'Golden|Shield|GS_' } | ForEach-Object {
  Write-Host ($_.TaskName + ' ' + $_.State)
}

Write-Host '===== 3) ERROR LOG COUNTS ====='
if (Test-Path 'storage\logs\errors.log') {
  $err = Get-Content 'storage\logs\errors.log' -ErrorAction SilentlyContinue
  Write-Host ('ERROR_LINES=' + $err.Count)
  Write-Host '--- TOP ERROR PATTERNS ---'
  $err | ForEach-Object {
    if ($_ -match 'InsufficientFunds') { 'InsufficientFunds' }
    elseif ($_ -match 'editMessageText') { 'Telegram editMessageText' }
    elseif ($_ -match 'message is not modified') { 'Telegram not modified' }
    elseif ($_ -match 'Conflict') { 'Telegram Conflict getUpdates' }
    elseif ($_ -match 'smart_exits') { 'smart_exits' }
    elseif ($_ -match 'Stop Loss|تعذر تأكيد') { 'SL confirm' }
    elseif ($_ -match 'Exception|Error|ERROR|Traceback') { 'OtherException' }
  } | Group-Object | Sort-Object Count -Descending | Select-Object -First 20 | ForEach-Object {
    Write-Host ($_.Count.ToString() + '  ' + $_.Name)
  }
  Write-Host '--- LAST 60 ERROR LINES ---'
  Get-Content 'storage\logs\errors.log' -Tail 60
} else { Write-Host 'NO errors.log' }

Write-Host '===== 4) STDOUT HINTS ====='
if (Test-Path 'storage\logs\bot_stdout.log') {
  Select-String -Path 'storage\logs\bot_stdout.log' -Pattern 'Emergency|Panic|Kill|رفض|فشل|خطأ|insufficient|closed_ghost|مراكز مفتوحة' |
    Select-Object -Last 40 | ForEach-Object { $_.Line }
}

Write-Host '===== 5) PYTHON HEALTH ====='
& $py -c @"
from config.settings import get_settings
from data.exchange_client import get_exchange
from database.connection import DatabaseConnection

s=get_settings()
print('env', s.env)
print('mode', s.execution_mode)
print('backend', s.execution_backend)
print('demo', s.binance_demo_trading)
print('manual_entry', s.manual_entry_required)
print('auto_min', s.auto_entry_min_percent)
print('max_pos', s.max_concurrent_positions)
print('mt5', getattr(s,'mt5_enabled', None))
print('telegram_token', bool(s.telegram_token))
print('telegram_chat', bool(s.telegram_chat_id))
print('db', s.db_path)

ex=get_exchange()
bal=ex.fetch_balance() or {}
usdt=bal.get('USDT') or {}
free=float(usdt.get('free') if isinstance(usdt, dict) else (usdt or 0))
total_u=float(usdt.get('total') if isinstance(usdt, dict) else (usdt or 0))
print(f'USDT_FREE={free:.4f} USDT_TOTAL={total_u:.4f}')
stables={'USDT','USDC','BUSD','FDUSD','TUSD','DAI','EUR','USD'}
assets=[]
for a,q in (bal.get('total') or {}).items():
  try: qq=float(q or 0)
  except: continue
  if a.upper() in stables or qq<=0: continue
  assets.append((a,qq))
print('ASSETS', len(assets))
for a,qq in sorted(assets):
  print(f'  {a}={qq}')

db=DatabaseConnection(s.db_path)
with db.connect() as conn:
  open_n=conn.execute(\"SELECT COUNT(*) c FROM trades WHERE status='open'\").fetchone()[0]
  closed_n=conn.execute(\"SELECT COUNT(*) c FROM trades WHERE status='closed'\").fetchone()[0]
  print('DB_OPEN', open_n, 'DB_CLOSED', closed_n)
  # mismatches: open in DB but no asset
  opens=conn.execute(\"SELECT symbol,amount,entry_price,stop_loss FROM trades WHERE status='open'\").fetchall()
  for r in opens:
    d=dict(r) if hasattr(r,'keys') else {'symbol':r[0],'amount':r[1]}
    sym=d['symbol']; base=sym.split('/')[0]
    qty=float((bal.get('total') or {}).get(base) or 0)
    print(f\"OPEN {sym} db_amt={d.get('amount')} exch_qty={qty} SL={d.get('stop_loss')}\")
  for r in conn.execute(\"SELECT symbol,pnl,exit_price,closed_at FROM trades WHERE status='closed' ORDER BY closed_at DESC LIMIT 5\").fetchall():
    print('CLOSED', dict(r) if hasattr(r,'keys') else r)
"@
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.getenv("WIN_HOST"),
        username=os.getenv("WIN_USER"),
        password=os.getenv("WIN_PASSWORD"),
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_full_audit.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=180,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    path = ROOT / "storage" / "logs" / "full_bot_audit.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out + "\nSTDERR\n" + err, encoding="utf-8")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", "replace").decode("ascii")[-2000:])
    print("SAVED", path)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
